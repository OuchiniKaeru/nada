from datetime import datetime, timedelta, date

from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.execution import Execution
from app.services.model_price_service import list_model_prices


async def get_metrics_overview(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            func.coalesce(func.sum(Execution.cost), 0),
            func.coalesce(func.sum(Execution.total_tokens), 0),
            func.coalesce(func.sum(Execution.duration_ms), 0),
            func.count(Execution.id),
        )
    )
    cost_total, tokens_total, duration_total, executions_count = result.one()
    return {
        "cost_total": float(cost_total),
        "tokens_total": int(tokens_total),
        "duration_total": int(duration_total),
        "executions_count": int(executions_count),
    }


async def get_metrics_daily(db: AsyncSession, days: int = 14) -> list[dict]:
    """Per-day token/cost/count aggregation for the dashboard graph."""
    weeks_cutoff = datetime.utcnow() - timedelta(days=max(1, int(days)))
    result = await db.execute(
        select(
            cast(Execution.created_at, Date).label("day"),
            func.coalesce(func.sum(Execution.total_tokens), 0),
            func.coalesce(func.sum(Execution.cost), 0),
            func.count(Execution.id),
        )
        .where(Execution.created_at >= weeks_cutoff)
        .group_by(cast(Execution.created_at, Date))
        .order_by(cast(Execution.created_at, Date).asc())
    )
    rows = result.all()
    by_day = {r.day.isoformat(): {"tokens": int(r[1]), "cost": float(r[2]), "count": int(r[3])} for r in rows}

    # Fill gaps so the frontend chart is continuous.
    out = []
    start = (datetime.utcnow() - timedelta(days=max(1, int(days)) - 1)).date()
    today = date.today()
    cursor = start
    while cursor <= today:
        item = by_day.get(cursor.isoformat(), {"tokens": 0, "cost": 0.0, "count": 0})
        out.append({"date": cursor.isoformat(), **item})
        cursor += timedelta(days=1)
    return out


async def get_models_usage(db: AsyncSession) -> list[dict]:
    """Per-model aggregated token/cost/count for the dashboard master table."""
    result = await db.execute(
        select(
            Execution.model,
            func.coalesce(func.sum(Execution.input_tokens), 0),
            func.coalesce(func.sum(Execution.output_tokens), 0),
            func.coalesce(func.sum(Execution.total_tokens), 0),
            func.coalesce(func.sum(Execution.cost), 0),
            func.count(Execution.id),
        )
        .group_by(Execution.model)
        .order_by(func.count(Execution.id).desc())
    )
    return [
        {
            "model": row[0] or "",
            "input_tokens": int(row[1]),
            "output_tokens": int(row[2]),
            "total_tokens": int(row[3]),
            "cost": float(row[4]),
            "count": int(row[5]),
        }
        for row in result.all()
    ]


async def get_model_prices(db: AsyncSession) -> list[dict]:
    return await list_model_prices(db)
