from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
import os
import asyncio

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./nada.db")


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    session = None
    try:
        session = AsyncSessionLocal()
        yield session
    finally:
        if session is not None:
            for method in (session.rollback, session.close):
                try:
                    await method()
                except (asyncio.CancelledError, BaseExceptionGroup):
                    pass
                except Exception:
                    pass
