"""Model cost master table.

Holds per-model USD prices per 1M tokens. Prices are seeded idempotently at
startup (see ``seed_model_prices``) so a fresh database always has a master
table, and are used as a fallback when a model provider does not report its own
cost (see ``compute_cost_from_prices`` / ``execution_service``).
"""
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model_price import ModelPrice

# USD per 1M tokens. Currency is USD. Values are approximate list prices for the
# major models the platform exposes (kept up to date with public pricing pages).
DEFAULT_PRICES: list[dict] = [
    # OpenAI
    {"provider": "openai", "model_id": "gpt-4o", "input_price": 2.50, "output_price": 10.00},
    {"provider": "openai", "model_id": "gpt-4o-mini", "input_price": 0.15, "output_price": 0.60},
    {"provider": "openai", "model_id": "gpt-4.1", "input_price": 2.00, "output_price": 8.00},
    {"provider": "openai", "model_id": "gpt-4.1-mini", "input_price": 0.40, "output_price": 1.60},
    {"provider": "openai", "model_id": "gpt-4.1-nano", "input_price": 0.10, "output_price": 0.40},
    {"provider": "openai", "model_id": "gpt-5.4", "input_price": 2.50, "output_price": 15.00},
    {"provider": "openai", "model_id": "gpt-5.4-mini", "input_price": 0.75, "output_price": 4.50},
    # Anthropic
    {"provider": "anthropic", "model_id": "claude-3-5-sonnet", "input_price": 3.00, "output_price": 15.00},
    {"provider": "anthropic", "model_id": "claude-3-5-haiku", "input_price": 0.80, "output_price": 4.00},
    {"provider": "anthropic", "model_id": "claude-3-7-sonnet", "input_price": 3.00, "output_price": 15.00},
    {"provider": "anthropic", "model_id": "claude-4-sonnet", "input_price": 3.00, "output_price": 15.00},
    {"provider": "anthropic", "model_id": "claude-5-sonnet", "input_price": 2.00, "output_price": 10.00},
    {"provider": "anthropic", "model_id": "claude-5-opus", "input_price": 5.00, "output_price": 25.00},
    # Google
    {"provider": "google", "model_id": "gemini-1.5-pro", "input_price": 1.25, "output_price": 5.00},
    {"provider": "google", "model_id": "gemini-1.5-flash", "input_price": 0.075, "output_price": 0.30},
    {"provider": "google", "model_id": "gemini-2.0-flash", "input_price": 0.10, "output_price": 0.40},
    {"provider": "google", "model_id": "gemini-2.5-pro", "input_price": 1.25, "output_price": 10.00},
    # DeepSeek
    {"provider": "deepseek", "model_id": "deepseek-chat", "input_price": 0.27, "output_price": 1.10},
    {"provider": "deepseek", "model_id": "deepseek-reasoner", "input_price": 0.55, "output_price": 2.19},
]


async def seed_model_prices(db: AsyncSession) -> None:
    """Idempotently upsert DEFAULT_PRICES into the master table."""
    for entry in DEFAULT_PRICES:
        result = await db.execute(
            select(ModelPrice).where(
                ModelPrice.provider == entry["provider"],
                ModelPrice.model_id == entry["model_id"],
            )
        )
        existing = result.scalar_one_or_none()
        if existing is None:
            db.add(
                ModelPrice(
                    id=str(uuid.uuid4()),
                    provider=entry["provider"],
                    model_id=entry["model_id"],
                    input_price=entry["input_price"],
                    output_price=entry["output_price"],
                    currency="USD",
                )
            )
    await db.commit()


async def list_model_prices(db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(ModelPrice).order_by(ModelPrice.provider.asc(), ModelPrice.model_id.asc())
    )
    return [
        {
            "id": row.id,
            "provider": row.provider,
            "model_id": row.model_id,
            "input_price": float(row.input_price),
            "output_price": float(row.output_price),
            "currency": row.currency or "USD",
        }
        for row in result.scalars().all()
    ]


async def find_price(db: AsyncSession, provider: str | None, model_id: str) -> ModelPrice | None:
    if not model_id:
        return None
    if provider:
        result = await db.execute(
            select(ModelPrice).where(
                ModelPrice.model_id == model_id,
                ModelPrice.provider == provider,
            )
        )
    else:
        # provider-agnostic: match on model_id alone (first row wins)
        result = await db.execute(
            select(ModelPrice).where(ModelPrice.model_id == model_id)
        )
    return result.scalar_one_or_none()


def compute_cost(input_tokens: int, output_tokens: int, input_price: float, output_price: float) -> float:
    """Cost in USD from token counts and per-1M-token prices."""
    return (input_tokens / 1_000_000 * input_price) + (output_tokens / 1_000_000 * output_price)
