"""バックグラウンドジョブマネージャー。

- asyncio.create_task でエージェント/スクワッド/Workflow を実行する。
- イベントに連番 (seq) を付けてインメモリバッファに保持し、
  Last-Event-ID (または ?since=) 指定の再接続時に欠落分を再生してから
  ライブ配信へ合流する = 再開可能な SSE。
- プロセス内完結のため、再起動を跨ぐ永続化はスコープ外 (単一ワーカー前提)。
"""
import asyncio
import time
import uuid
from collections import deque

_BUFFER_MAX = 2000

# job_id -> {"status": ..., "events": deque[(seq, json_str)], "subscribers": set[asyncio.Queue], "result": ...}
_jobs: dict = {}


class JobNotFound(Exception):
    pass


def create_job(kind: str, ref_id: str, message: str, user_id: str) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "id": job_id,
        "kind": kind,
        "ref_id": ref_id,
        "message": message,
        "user_id": user_id,
        "status": "running",
        "seq": 0,
        "events": deque(maxlen=_BUFFER_MAX),
        "first_seq": None,
        "subscribers": set(),
        "created_at": time.time(),
    }
    return job_id


def get_job(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise JobNotFound(job_id)
    return job


def list_jobs(user_id: str) -> list[dict]:
    return [
        {
            "id": j["id"],
            "kind": j["kind"],
            "ref_id": j["ref_id"],
            "status": j["status"],
            "created_at": j["created_at"],
        }
        for j in _jobs.values()
        if j["user_id"] == user_id
    ]


def publish_event(job_id: str, payload: dict) -> int:
    """イベントを記録し、購読者へ即時配信する。seq を返す。"""
    job = get_job(job_id)
    job["seq"] += 1
    seq = job["seq"]
    if job["first_seq"] is None:
        job["first_seq"] = seq
    item = (seq, payload)
    job["events"].append(item)

    for q in list(job["subscribers"]):
        try:
            q.put_nowait(item)
        except asyncio.QueueFull:
            pass
    return seq


def finish_job(job_id: str, status: str = "completed", result_summary: str | None = None):
    job = get_job(job_id)
    job["status"] = status
    if result_summary is not None:
        job["result_summary"] = result_summary
    # 終了マーカーを全購読者へ
    end = _END_MARKER
    for q in list(job["subscribers"]):
        try:
            q.put_nowait((-1, end))
        except asyncio.QueueFull:
            pass


_END_MARKER = object()


async def cancel_job(job_id: str) -> bool:
    job = get_job(job_id)
    task = job.get("task")
    if task and not task.done():
        task.cancel()
        return True
    return False


async def stream_events(job_id: str, since_seq: int = 0):
    """job のイベントを SSE 用にストリームする非同期ジェネレーター。

    since_seq 以降の履歴を再生してからライブ接続に合流する。
    """
    job = get_job(job_id)
    q: asyncio.Queue = asyncio.Queue(maxsize=1000)

    # 履歴再生 (登録と再生の間の取りこぼしを避けるため先に subscriber 登録)
    job["subscribers"].add(q)
    try:
        replayed = [(seq, ev) for seq, ev in job["events"] if seq > since_seq]
        for seq, ev in replayed:
            yield seq, ev

        # 完了済みなら履歴だけで終了
        if job["status"] != "running":
            return

        seen_max = replayed[-1][0] if replayed else since_seq
        while True:
            seq, ev = await q.get()
            if seq == -1 and ev is _END_MARKER:
                break
            if isinstance(seq, int) and seq > seen_max:
                yield seq, ev
            if job["status"] != "running" and q.empty():
                break
    finally:
        job["subscribers"].discard(q)
