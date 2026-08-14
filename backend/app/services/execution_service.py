import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution
from app.services.model_price_service import find_price, compute_cost


async def record_execution(
    db: AsyncSession,
    *,
    user_id: str,
    agent_id: str = "",
    session_id: str | None = None,
    squad_id: str | None = None,
    model: str = "",
    usage: dict | None = None,
) -> Execution:
    """Record one agent/team execution for the dashboard metrics.

    Fields missing from ``usage`` default to zero so a metrics row is always
    created (the dashboard "回数/コスト/トークン/作業時間" count requires a row
    even when the model reports no token accounting).
    """
    usage = usage or {}
    input_tokens = int(usage.get("input_tokens") or 0)
    output_tokens = int(usage.get("output_tokens") or 0)
    cost = float(usage.get("cost") or 0.0)
    model = model or usage.get("model") or ""

    # When the provider reported no cost but the model is in the master price
    # table, compute it from token usage so the dashboard always reflects a cost.
    if cost <= 0 and model:
        price = await find_price(db, None, model)
        if price is not None:
            cost = compute_cost(input_tokens, output_tokens, price.input_price, price.output_price)

    execution = Execution(
        id=str(uuid.uuid4()),
        user_id=user_id,
        agent_id=agent_id,
        session_id=session_id,
        squad_id=squad_id,
        model=model or "",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=int(usage.get("total_tokens") or 0),
        cost=cost,
        duration_ms=int(usage.get("duration_ms") or 0),
        status="success",
    )
    db.add(execution)
    await db.commit()
    return execution