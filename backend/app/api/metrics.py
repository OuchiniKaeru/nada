from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user, get_db
from app.services.metrics_service import (
    get_metrics_overview,
    get_metrics_daily,
    get_models_usage,
    get_model_prices,
)

router = APIRouter()

@router.get("/metrics/overview")
async def metrics_overview(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_metrics_overview(db)

@router.get("/metrics/daily")
async def metrics_daily(
    days: int = Query(14, ge=1, le=90),
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_metrics_daily(db, days)

@router.get("/metrics/models")
async def metrics_models(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_models_usage(db)

@router.get("/metrics/prices")
async def metrics_prices(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    return await get_model_prices(db)
