"""基本的なサンプルリソースのシード (冪等)。

起動時に system_prompt / rule / tool / hook / loop の基本セットを登録する。
既存リソースと名前が重複する場合はスキップするため、毎回実行して安全。
"""
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.resource import Resource
from app.services import config_store

logger = logging.getLogger(__name__)

# visibility="public" なので全ユーザーに表示される
SAMPLE_OWNER_ID = "system-samples"


SAMPLE_RESOURCES = [
    # ---- システムプロンプト (markdown, フロントマターに prompt) ----
    {
        "key": "sample-sp-concise",
        "type": "system_prompt",
        "name": "簡潔な回答",
        "description": "短く要点だけ答えるサンプルシステムプロンプト",
        "format": "markdown",
        "text": "---\nprompt: あなたは簡潔な回答を心がけるアシスタントです。結論を最初に述べ、余計な前置きや繰り返しを避け、可能な限り箇条書きで回答してください。不明な点は推測せず質問してください。\n---\n# 簡潔な回答\n",
    },
    {
        "key": "sample-sp-friendly",
        "description": "丁寧でフレンドリーな口調のサンプルシステムプロンプト",
        "type": "system_prompt",
        "name": "フレンドリーな回答",
        "format": "markdown",
        "text": "---\nprompt: あなたは丁寧で親しみやすいアシスタントです。相手を励ましながら、初心者にもわかる平易な言葉で説明してください。必要に応じて例え話を使い、最後に一言励ましのメッセージを添えてください。\n---\n# フレンドリーな回答\n",
    },
    {
        "key": "sample-sp-code",
        "type": "system_prompt",
        "name": "コードレビュー重視",
        "description": "コードレビュー観点での回答に特化したサンプル",
        "format": "markdown",
        "text": "---\nprompt: あなたはシニアソフトウェアエンジニアです。コードを示されたら、バグ・セキュリティ・パフォーマンス・可読性の4観点でレビューしてください。指摘には必ず修正後のコード例を添えてください。\n---\n# コードレビュー\n",
    },
    # ---- Rule (markdown, フロントマターに rule) ----
    {
        "key": "sample-rule-japanese",
        "type": "rule",
        "name": "日本語で回答",
        "description": "常に日本語で応答させるサンプルルール",
        "format": "markdown",
        "text": "---\nrule: 質問がどの言語で書かれていても、必ず日本語で回答してください。コードやライブラリ名は原文のまま残して構いません。\n---\n# 日本語ルール\n",
    },
    {
        "key": "sample-rule-no-secrets",
        "type": "rule",
        "name": "秘密情報を扱わない",
        "description": "認証情報などの出力を禁止するサンプルルール",
        "format": "markdown",
        "text": "---\nrule: APIキー・パスワード・トークンなどの秘密情報は絶対に出力しないでください。入力に含まれていた場合もその値を引用せず、「秘密情報のため省略」と表現してください。\n---\n# 秘密情報保護\n",
    },
    {
        "key": "sample-rule-cite-source",
        "type": "rule",
        "name": "出典を明示",
        "description": "根拠を示すことを促すサンプルルール",
        "format": "markdown",
        "text": "---\nrule: 事実を述べるときは、その根拠(ドキュメント名・URL・コードの場所など)を必ず添えてください。根拠がない場合は「推測」と明示してください。\n---\n# 出典明示\n",
    },
    # ---- Tool (json: agno toolkit 名) ----
    {
        "key": "sample-tool-websearch",
        "type": "tool",
        "name": "Web検索",
        "description": "WebSearchTools を使えるようにするサンプルツール",
        "format": "json",
        "text": '{"tools": [{"name": "WebSearchTools"}]}',
    },
    {
        "key": "sample-tool-shell",
        "type": "tool",
        "name": "シェル実行",
        "description": "ShellTools を使えるようにするサンプルツール",
        "format": "json",
        "text": '{"tools": [{"name": "ShellTools"}]}',
    },
    {
        "key": "sample-tool-fs",
        "type": "tool",
        "name": "ファイル操作",
        "description": "LocalFileSystemTools を使えるようにするサンプルツール",
        "format": "json",
        "text": '{"tools": [{"name": "LocalFileSystemTools"}]}',
    },
    {
        "key": "sample-tool-python",
        "type": "tool",
        "name": "Python実行",
        "description": "PythonTools を使えるようにするサンプルツール",
        "format": "json",
        "text": '{"tools": [{"name": "PythonTools"}]}',
    },
    # ---- Hooks (json) ----
    {
        "key": "sample-hook-log-input",
        "type": "hook",
        "name": "入力ログ記録",
        "description": "エージェント実行前に入力をログに記録するサンプルフック",
        "format": "json",
        "text": '{"hook_type": "pre_run", "action": "log", "message": "ユーザー入力をログに記録します"}',
    },
    {
        "key": "sample-hook-guard-pii",
        "type": "hook",
        "name": "個人情報チェック",
        "description": "実行前に個人情報の送信を警告するサンプルフック",
        "format": "json",
        "text": '{"hook_type": "pre_run", "action": "warn_pii", "message": "入力にメールアドレスや電話番号が含まれる場合は実行前に確認する"}',
    },
    {
        "key": "sample-hook-post-notify",
        "type": "hook",
        "name": "完了通知",
        "description": "タスク完了時に通知するサンプルフック",
        "format": "json",
        "text": '{"hook_type": "post_run", "action": "notify", "message": "タスクが完了しました"}',
    },
    # ---- Loop (markdown) ----
    {
        "key": "sample-loop-improve",
        "type": "loop",
        "name": "改善ループ",
        "description": "生成→自己評価→改善を繰り返すサンプルループ",
        "format": "markdown",
        "text": "---\nloop:\n  max_iterations: 3\n  stop_condition: 自己評価が9割以上のとき終了\n---\n# 改善ループ\n\n1. 回答案を作成する\n2. 「正確性/網羅性/簡潔さ」の3点で10点満点の自己評価をする\n3. 9点未満なら改善して再提出する\n",
    },
    {
        "key": "sample-loop-retry",
        "type": "loop",
        "name": "リトライループ",
        "description": "失敗時に再試行するサンプルループ",
        "format": "markdown",
        "text": "---\nloop:\n  max_iterations: 5\n  stop_condition: タスク成功時\n---\n# リトライループ\n\n1. タスクを実行する\n2. エラーの場合、原因を1文で分析する\n3. 分析を踏まえて手法を変えて再試行する\n",
    },
]


async def seed_sample_resources(db: AsyncSession) -> int:
    """サンプルリソースを登録する (同名の resources があればスキップ)。戻り値は登録件数。"""
    created = 0
    existing_names = set()
    result = await db.execute(select(Resource.name).where(Resource.type.in_(
        {s["type"] for s in SAMPLE_RESOURCES}
    )))
    for (name,) in result.all():
        existing_names.add(name)

    for spec in SAMPLE_RESOURCES:
        if spec["name"] in existing_names:
            continue
        resource_id = str(uuid.uuid4())
        try:
            path = config_store.save_config(spec["type"], resource_id, spec["format"], spec["text"])
            db.add(Resource(
                id=resource_id,
                type=spec["type"],
                name=spec["name"],
                description=spec["description"],
                visibility="public",
                config_format=spec["format"],
                config_path=str(path),
                owner_id=SAMPLE_OWNER_ID,
            ))
            created += 1
        except Exception:
            logger.exception("[seed_samples] %s failed", spec["key"])

    if created:
        await db.commit()
        logger.info("[seed_samples] created %d sample resources", created)
    return created
