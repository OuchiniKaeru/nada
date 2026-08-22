"""Workflow 実行エンジン。

steps を順次実行し、前ステップの出力を次の入力へ単純連結する。
各ステップの進捗をイベントとして yield する (SSE 配信用)。
"""
import time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent as AgentModel
from app.models.squad import Squad
from app.runtime.agent_runtime import AgentRuntime, SquadChatRuntime


async def _run_step(db: AsyncSession, user_id: str, step: dict, message: str) -> str:
    kind = step.get("kind")
    ref_id = step.get("ref_id")
    if not ref_id:
        raise ValueError("step.ref_id が指定されていません")

    parts: list[str] = []
    if kind == "squad":
        result = await db.execute(select(Squad).where(Squad.id == ref_id))
        squad = result.scalar_one_or_none()
        if not squad:
            raise ValueError(f"スクワッドが見つかりません: {ref_id}")
        runtime = SquadChatRuntime(squad, db)
        async for chunk in runtime.astream(message):
            parts.append(chunk)
    else:
        result = await db.execute(select(AgentModel).where(AgentModel.id == ref_id))
        agent = result.scalar_one_or_none()
        if not agent:
            raise ValueError(f"エージェントが見つかりません: {ref_id}")
        runtime = AgentRuntime(ref_id, db, user_id=user_id)
        async for chunk in runtime.astream(message):
            parts.append(chunk)

    return "".join(parts).strip() or "(no response)"


async def run_workflow_stream(db: AsyncSession, workflow, user_id: str, message: str):
    """Workflow を実行し、進捗イベントを yield する非同期ジェネレーター。

    イベント形式:
      {"type": "step_started",  "index": i, "kind": ..., "name": ...}
      {"type": "delta",         "index": i, "content": chunk}
      {"type": "step_completed","index": i, "output_length": n}
      {"type": "workflow_done", "outputs": [...], "duration_ms": n}
      {"type": "error",         "message": ...}
    """
    start = time.monotonic()
    steps = workflow.steps or []
    if not steps:
        yield {"type": "error", "message": "Workflowにステップが定義されていません。"}
        return

    current = message
    outputs: list[str] = []

    for i, step in enumerate(steps):
        # step 名を解決 (表示用)
        name = ""
        try:
            if step.get("kind") == "squad":
                row = await db.execute(select(Squad.name).where(Squad.id == step.get("ref_id")))
                name = row.scalar_one_or_none() or ""
            else:
                row = await db.execute(select(AgentModel.title).where(AgentModel.id == step.get("ref_id")))
                name = row.scalar_one_or_none() or ""
        except Exception:
            name = ""

        yield {"type": "step_started", "index": i, "kind": step.get("kind"), "name": name}

        try:
            output = await _run_step(db, user_id, step, current)
        except Exception as exc:
            yield {"type": "error", "message": f"ステップ{i + 1}でエラーが発生しました: {exc}"}
            return

        outputs.append(output)
        current = f"{current}\n\n{output}"  # 前ステップ出力を単純連結
        yield {"type": "step_completed", "index": i, "output": output}

    yield {
        "type": "workflow_done",
        "outputs": outputs,
        "duration_ms": int((time.monotonic() - start) * 1000),
    }
