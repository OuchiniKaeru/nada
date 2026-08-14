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
from app.services.agent_factory import init_agno_db
from app.services.model_price_service import seed_model_prices
from app.core.database import AsyncSessionLocal


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Idempotently seed the model cost master table. Wrapped defensively so a
    # database that hasn't had migrations run yet doesn't prevent startup.
    try:
        async with AsyncSessionLocal() as session:
            await seed_model_prices(session)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("model price seeding skipped")
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


@app.get("/health")
async def health():
    return {"status": "ok"}