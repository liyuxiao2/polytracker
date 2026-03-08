from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import datetime
from app.core.database import get_session
from app.domains.traders.schema import (
    MarketWatchItem,
    TradeResponse,
    TrackedMarketResponse,
    TrackedMarketCreate,
    DiscoverMarketsRequest,
    MarketSnapshotResponse,
    PriceHistoryResponse,
    BackfillRequest
)
from app.domains.markets.service import MarketService

router = APIRouter()
market_service = MarketService()

@router.get("/markets/watch", response_model=List[MarketWatchItem])
async def get_market_watch(
    category: Optional[str] = Query(None),
    sort_by: str = Query("suspicion_score", regex="^(suspicion_score|volatility_score|total_volume|suspicious_trades_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session)
):
    """Get markets sorted by suspicious activity or volatility."""
    return await market_service.get_market_watch(session, category, sort_by, sort_order, limit)

@router.get("/markets/{market_id}/trades", response_model=List[TradeResponse])
async def get_market_trades(
    market_id: str,
    limit: int = Query(50, le=10000, description="Max trades to return (up to 10000 for all-time)"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    session: AsyncSession = Depends(get_session)
):
    """Get trade history for a specific market."""
    return await market_service.get_market_trades(session, market_id, page, limit)

@router.get("/markets/{market_id}/trades/count")
async def get_market_trades_count(
    market_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get total trade count for a market."""
    return await market_service.get_market_trades_count(session, market_id)

@router.get("/backtesting/tracked-markets", response_model=List[TrackedMarketResponse])
async def get_tracked_markets(
    category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session)
):
    """Get list of markets being tracked for backtesting snapshots."""
    return await market_service.get_tracked_markets(session, category, active_only, limit)

@router.post("/backtesting/track-market", response_model=TrackedMarketResponse)
async def add_tracked_market(
    market: TrackedMarketCreate
):
    """Add a market to the tracking list for backtesting data collection."""
    return await market_service.add_tracked_market(market)

@router.post("/backtesting/discover-markets", response_model=List[TrackedMarketResponse])
async def discover_markets(
    request: DiscoverMarketsRequest
):
    """Auto-discover high-liquidity markets to track based on categories."""
    return await market_service.discover_markets(request)

@router.delete("/backtesting/tracked-markets/{market_id}")
async def remove_tracked_market(
    market_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Remove a market from tracking (sets is_active=False)."""
    return await market_service.remove_tracked_market(session, market_id)

@router.get("/backtesting/snapshots", response_model=List[MarketSnapshotResponse])
async def get_market_snapshots(
    market_id: str = Query(..., description="Market condition_id"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(1000, le=10000),
    session: AsyncSession = Depends(get_session)
):
    """Get order book snapshots for a market within a time range."""
    return await market_service.get_market_snapshots(session, market_id, start_time, end_time, limit)

@router.get("/backtesting/price-history", response_model=List[PriceHistoryResponse])
async def get_price_history(
    market_id: str = Query(..., description="Market condition_id"),
    outcome: Optional[str] = Query(None, description="YES or NO"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    interval: Optional[str] = Query(None, description="Filter by interval (1m, 5m, 1h, etc.)"),
    limit: int = Query(5000, le=50000),
    session: AsyncSession = Depends(get_session)
):
    """Get historical price data for a market."""
    return await market_service.get_price_history(session, market_id, outcome, start_time, end_time, interval, limit)

@router.post("/backtesting/backfill")
async def backfill_price_history(
    request: BackfillRequest
):
    """Backfill historical price data for a market from the CLOB API."""
    return await market_service.backfill_price_history(request)

@router.post("/backfill/trades")
async def backfill_trades(
    max_pages: int = Query(100, le=500, description="Maximum pages to fetch (500 trades/page)"),
    market_ids: Optional[List[str]] = Query(None, description="Optional list of market IDs to filter for"),
):
    """Backfill historical trades from Polymarket API."""
    return await market_service.backfill_trades(max_pages, market_ids)
