from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_session
from app.schemas.trader import DashboardStats
from app.services.system_service import SystemService

router = APIRouter()
system_service = SystemService()

@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_session)
):
    """Get high-level dashboard statistics."""
    return await system_service.get_dashboard_stats(session)

@router.post("/resolve/bulk")
async def bulk_resolve_trades(
    concurrency: int = Query(10, le=50, description="Max concurrent API calls"),
):
    """Bulk-resolve all unresolved trades."""
    from app.services.market_service import MarketService
    market_service = MarketService()
    return await market_service.bulk_resolve_trades(concurrency)

@router.get("/backtesting/stats")
async def get_backtesting_stats(
    session: AsyncSession = Depends(get_session)
):
    """Get statistics about backtesting data collection."""
    from app.services.market_service import MarketService
    market_service = MarketService()
    return await market_service.get_backtesting_stats(session)
