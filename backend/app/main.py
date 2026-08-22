from dotenv import load_dotenv

load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api import agents
from app.api import auth
from app.api import chat
from app.api import skills
from app.api import mcps
from app.api import squads
from app.api import attachments
from app.api import metrics
from app.api import resources
from app.api import workflows
from app.api import jobs
from app.services.agent_factory import init_agno_db
from app.services.model_price_service import seed_model_prices
from app.core.database import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    def _import_all_models():
        # 全モデルを metadata に登録するために models を import
        import app.models.user  # noqa: F401
        import app.models.agent  # noqa: F401
        import app.models.agent_permission  # noqa: F401
        import app.models.skill  # noqa: F401
        import app.models.mcp  # noqa: F401
        import app.models.squad  # noqa: F401
        import app.models.squad_member  # noqa: F401
        import app.models.session  # noqa: F401
        import app.models.message  # noqa: F401
        import app.models.attachment  # noqa: F401
        import app.models.execution  # noqa: F401
        import app.models.execution_agent  # noqa: F401
        import app.models.model_registry  # noqa: F401
        import app.models.model_price  # noqa: F401
        import app.models.resource  # noqa: F401
        import app.models.workflow  # noqa: F401

    # SQLite (Dockerなしのローカル実行) の場合は起動時にテーブルを自動作成する。
    # PostgreSQL (Docker Compose) 環境では Alembic マイグレーションが正なので、
    # create_all を実行しない(既存運用を壊さない)。
    import os
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nada.db")
    if not db_url or db_url.startswith("sqlite"):
        try:
            from app.core.database import Base, engine
            _import_all_models()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("sqlite create_all skipped")

    # 新テーブル (resources / resource_links / workflows) の存在保証。
    # Alembic マイグレーション (094/095) が未実行の既存 Postgres DB でも
    # 動くように、checkfirst=True の create_all で欠落テーブルだけ作成する。
    # 既存テーブルには一切触れないため Alembic 運用と衝突しない。
    try:
        from app.core.database import Base, engine
        _import_all_models()
        async with engine.begin() as conn:
            await conn.run_sync(lambda sync_conn: Base.metadata.create_all(
                sync_conn,
                tables=[
                    Base.metadata.tables["resources"],
                    Base.metadata.tables["resource_links"],
                    Base.metadata.tables["workflows"],
                ],
                checkfirst=True,
            ))
    except Exception:
        import logging
        logging.getLogger(__name__).exception("new table creation skipped")

    # Idempotently seed the model cost master table. Wrapped defensively so a
    # database that hasn't had migrations run yet doesn't prevent startup.
    try:
        async with AsyncSessionLocal() as session:
            await seed_model_prices(session)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("model price seeding skipped")

    # 既存 Skill/MCP レコードを新方式 (resources + 設定ファイル) へ移行する。
    # 冪等なので毎回起動時に実行してよい。失敗しても起動は妨げない。
    try:
        from app.services.resource_migration import migrate_existing_skills_and_mcps
        async with AsyncSessionLocal() as session:
            stats = await migrate_existing_skills_and_mcps(session)
            if stats["skills_migrated"] or stats["mcps_migrated"]:
                import logging
                logging.getLogger(__name__).info(
                    "[resource_migration] migrated: %s", stats
                )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("resource migration skipped")

    # 基本的なサンプルリソース (システムプロンプト/Rule/Tool/Hooks/Loop) を登録する。
    # 冪等 (同名リソースがあればスキップ)。失敗しても起動は妨げない。
    try:
        from app.services.sample_resources import seed_sample_resources
        async with AsyncSessionLocal() as session:
            await seed_sample_resources(session)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("sample resource seeding skipped")
    yield


init_agno_db()

app = FastAPI(title="NADA AI Agent Platform", lifespan=lifespan)


@app.exception_handler(Exception)
async def runtime_exception_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(agents.router, prefix="/api", tags=["agents"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(skills.router, prefix="/api", tags=["skills"])
app.include_router(mcps.router, prefix="/api", tags=["mcps"])
app.include_router(squads.router, prefix="/api", tags=["squads"])
app.include_router(attachments.router, prefix="/api", tags=["attachments"])
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(resources.router, prefix="/api", tags=["resources"])
app.include_router(workflows.router, prefix="/api", tags=["workflows"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])


@app.get("/health")
async def health():
    return {"status": "ok"}