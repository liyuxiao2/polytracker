from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.database import get_session
from app.domains.traders.schema import TraderProfileResponse, TraderListItem, TrendingTrade, TradeResponse
from app.domains.traders.service import TraderService

router = APIRouter()
trader_service = TraderService()

@router.get("/traders", response_model=List[TraderListItem])
async def get_flagged_traders(
    limit: int = Query(50, le=200),
    min_score: float = Query(0, ge=0, le=100),
    session: AsyncSession = Depends(get_session)
):
    """Get list of flagged traders sorted by insider score."""
    return await trader_service.get_flagged_traders(session, limit, min_score)

@router.get("/trades/trending", response_model=List[TrendingTrade])
async def get_trending_trades(
    min_size: float = Query(5000, ge=0),
    hours: int = Query(24, ge=1, le=168),
    page: int = Query(1, ge=1),
    limit: int = Query(50, le=500),
    sort_by: str = Query("timestamp", regex="^(timestamp|size|z_score|win_loss|deviation)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session)
):
    """Get real-time stream of trades filtered by size, high deviation, or winning large bets."""
    return await trader_service.get_trending_trades(session, min_size, hours, page, limit, sort_by, sort_order)

@router.get("/trader/{address}", response_model=TraderProfileResponse)
async def get_trader_profile(
    address: str,
    session: AsyncSession = Depends(get_session)
):
    """Get detailed historical profile for a specific trader."""
    return await trader_service.get_trader_profile(session, address)

@router.get("/trader/{address}/trades", response_model=List[TradeResponse])
async def get_trader_trades(
    address: str,
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session)
):
    """Get trade history for a specific trader."""
    return await trader_service.get_trader_trades(session, address, limit)

@router.get("/trader/{address}/open-positions", response_model=List[TradeResponse])
async def get_trader_open_positions(
    address: str,
    min_unrealized_pnl: Optional[float] = Query(None, description="Filter positions with unrealized P&L >= this value"),
    session: AsyncSession = Depends(get_session)
):
    """Get current open positions (unresolved trades) with unrealized P&L for a specific trader."""
    return await trader_service.get_trader_open_positions(session, address, min_unrealized_pnl)
