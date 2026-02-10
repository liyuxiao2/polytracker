from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, and_
from datetime import datetime, timedelta
from typing import List, Optional
from app.models.database import get_session, Trade, TraderProfile, Market, TrackedMarket, MarketSnapshot, PriceHistory
from app.schemas.trader import (
    TraderProfileResponse,
    TraderListItem,
    TrendingTrade,
    DashboardStats,
    TradeResponse,
    MarketWatchItem,
    TrackedMarketResponse,
    TrackedMarketCreate,
    MarketSnapshotResponse,
    PriceHistoryResponse,
    DiscoverMarketsRequest,
    BackfillRequest
)
from app.services.insider_detector import InsiderDetector

router = APIRouter()
detector = InsiderDetector()


@router.get("/traders", response_model=List[TraderListItem])
async def get_flagged_traders(
    limit: int = Query(50, le=200),
    min_score: float = Query(0, ge=0, le=100),
    session: AsyncSession = Depends(get_session)
):
    """
    Get list of flagged traders sorted by insider score.
    """
    result = await session.execute(
        select(TraderProfile)
        .where(TraderProfile.insider_score >= min_score)
        .order_by(desc(TraderProfile.insider_score))
        .limit(limit)
    )
    profiles = result.scalars().all()

    # Get last trade time for each trader
    traders_list = []
    for profile in profiles:
        last_trade_result = await session.execute(
            select(Trade.timestamp)
            .where(Trade.wallet_address == profile.wallet_address)
            .order_by(desc(Trade.timestamp))
            .limit(1)
        )
        last_trade = last_trade_result.scalar_one_or_none()

        traders_list.append(TraderListItem(
            wallet_address=profile.wallet_address,
            insider_score=profile.insider_score,
            total_trades=profile.total_trades,
            avg_bet_size=profile.avg_bet_size,
            win_rate=profile.win_rate,
            total_pnl=profile.total_pnl,
            flagged_trades_count=profile.flagged_trades_count,
            flagged_wins_count=profile.flagged_wins_count,
            last_trade_time=last_trade
        ))

    return traders_list


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
    """
    Get real-time stream of trades filtered by size, high deviation, or winning large bets.
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    # Base query: Join with TraderProfile to calculate deviation during sort/select
    query = select(Trade, TraderProfile).outerjoin(
        TraderProfile, Trade.wallet_address == TraderProfile.wallet_address
    ).where(
        and_(
            Trade.timestamp >= cutoff_time,
            (
                (Trade.is_flagged == True) |
                (Trade.trade_size_usd >= min_size) |
                ((Trade.is_win == True) & (Trade.trade_size_usd >= 10000))
            )
        )
    )

    # Sorting
    if sort_by == "size":
        sort_col = Trade.trade_size_usd
    elif sort_by == "z_score":
        sort_col = Trade.z_score
    elif sort_by == "win_loss":
        sort_col = Trade.is_win
    elif sort_by == "deviation":
        # Sort by deviation percentage: (trade_size - avg_bet) / avg_bet
        # Handle division by zero/null using case
        sort_col = func.case(
            (TraderProfile.avg_bet_size > 0, (Trade.trade_size_usd - TraderProfile.avg_bet_size) / TraderProfile.avg_bet_size),
            else_=0
        )
    else: # timestamp
        sort_col = Trade.timestamp

    if sort_order == "desc":
        if sort_by == "win_loss":
             query = query.order_by(desc(Trade.is_win).nullslast())
        else:
             query = query.order_by(desc(sort_col))
    else:
        if sort_by == "win_loss":
             query = query.order_by(asc(Trade.is_win).nullslast())
        else:
            query = query.order_by(asc(sort_col))

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    rows = result.all()

    trending = []
    for trade, profile in rows:
        deviation_pct = 0.0
        if profile and profile.avg_bet_size > 0:
             deviation_pct = ((trade.trade_size_usd - profile.avg_bet_size) / profile.avg_bet_size) * 100

        trending.append(TrendingTrade(
            wallet_address=trade.wallet_address,
            market_name=trade.market_name,
            trade_size_usd=trade.trade_size_usd,
            z_score=trade.z_score or 0.0,
            timestamp=trade.timestamp,
            deviation_percentage=deviation_pct,
            is_win=trade.is_win,
            flag_reason=trade.flag_reason,
            # Trade details
            outcome=trade.outcome,
            side=trade.side,
            price=trade.price,
            pnl_usd=trade.pnl_usd,
            # Timing analysis
            hours_before_resolution=trade.hours_before_resolution,
            trade_hour_utc=trade.trade_hour_utc
        ))

    return trending


@router.get("/trader/{address}", response_model=TraderProfileResponse)
async def get_trader_profile(
    address: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Get detailed historical profile for a specific trader.
    """
    result = await session.execute(
        select(TraderProfile).where(TraderProfile.wallet_address == address)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        # If no profile exists, update it
        await detector.update_trader_profile(address, session)
        result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == address)
        )
        profile = result.scalar_one_or_none()

    if not profile:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Trader not found")

    return TraderProfileResponse.model_validate(profile)


@router.get("/trader/{address}/trades", response_model=List[TradeResponse])
async def get_trader_trades(
    address: str,
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session)
):
    """
    Get trade history for a specific trader.
    """
    result = await session.execute(
        select(Trade)
        .where(Trade.wallet_address == address)
        .order_by(desc(Trade.timestamp))
        .limit(limit)
    )
    trades = result.scalars().all()

    return [TradeResponse.model_validate(trade) for trade in trades]


@router.get("/trader/{address}/open-positions", response_model=List[TradeResponse])
async def get_trader_open_positions(
    address: str,
    min_unrealized_pnl: Optional[float] = Query(None, description="Filter positions with unrealized P&L >= this value"),
    session: AsyncSession = Depends(get_session)
):
    """
    Get current open positions (unresolved trades) with unrealized P&L for a specific trader.
    Useful for seeing what a trader is currently betting on and how they're performing in real-time.
    """
    query = select(Trade).where(
        (Trade.wallet_address == address) &
        (Trade.is_win.is_(None)) &
        (Trade.unrealized_pnl_usd.isnot(None))
    ).order_by(desc(Trade.unrealized_pnl_usd))

    if min_unrealized_pnl is not None:
        query = query.where(Trade.unrealized_pnl_usd >= min_unrealized_pnl)

    result = await session.execute(query)
    trades = result.scalars().all()

    return [TradeResponse.model_validate(trade) for trade in trades]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    session: AsyncSession = Depends(get_session)
):
    """
    Get high-level dashboard statistics.
    """
    # Total whales tracked (traders with score > 50)
    whales_result = await session.execute(
        select(func.count(TraderProfile.id))
        .where(TraderProfile.insider_score >= 50)
    )
    total_whales = whales_result.scalar() or 0

    # High-signal alerts today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    alerts_result = await session.execute(
        select(func.count(Trade.id))
        .where(
            (Trade.is_flagged == True) &
            (Trade.timestamp >= today_start)
        )
    )
    alerts_today = alerts_result.scalar() or 0

    # Total trades monitored
    total_trades_result = await session.execute(
        select(func.count(Trade.id))
    )
    total_trades = total_trades_result.scalar() or 0

    # Average insider score
    avg_score_result = await session.execute(
        select(func.avg(TraderProfile.insider_score))
    )
    avg_score = avg_score_result.scalar() or 0.0

    # Resolved trades (where is_win is not null) - these are trades we can verify won/lost
    resolved_result = await session.execute(
        select(func.count(Trade.id))
        .where(Trade.is_win.isnot(None))
    )
    total_resolved = resolved_result.scalar() or 0

    # Average win rate from resolved flagged trades
    flagged_resolved_result = await session.execute(
        select(
            func.count(Trade.id).filter(Trade.is_win == True),
            func.count(Trade.id)
        )
        .where(
            (Trade.is_flagged == True) &
            (Trade.is_win.isnot(None))
        )
    )
    row = flagged_resolved_result.one()
    wins = row[0] or 0
    total_flagged_resolved = row[1] or 0
    avg_win_rate = (wins / total_flagged_resolved * 100) if total_flagged_resolved > 0 else 0.0

    # NEW: Total volume in last 24 hours
    cutoff_24h = datetime.utcnow() - timedelta(hours=24)
    volume_result = await session.execute(
        select(func.sum(Trade.trade_size_usd))
        .where(Trade.timestamp >= cutoff_24h)
    )
    total_volume_24h = volume_result.scalar() or 0.0

    # NEW: Total PnL from flagged trades
    pnl_result = await session.execute(
        select(func.sum(Trade.pnl_usd))
        .where(
            (Trade.is_flagged == True) &
            (Trade.pnl_usd.isnot(None))
        )
    )
    total_pnl_flagged = pnl_result.scalar() or 0.0

    # NEW: Unrealized P&L statistics (open positions)
    open_positions_result = await session.execute(
        select(func.count(Trade.id))
        .where((Trade.is_win.is_(None)) & (Trade.unrealized_pnl_usd.isnot(None)))
    )
    total_open_positions = open_positions_result.scalar() or 0

    unrealized_pnl_result = await session.execute(
        select(func.sum(Trade.unrealized_pnl_usd))
        .where(Trade.unrealized_pnl_usd.isnot(None))
    )
    total_unrealized_pnl = unrealized_pnl_result.scalar() or 0.0

    avg_unrealized_roi_result = await session.execute(
        select(func.avg(TraderProfile.unrealized_roi))
        .where(TraderProfile.open_positions_count > 0)
    )
    avg_unrealized_roi = avg_unrealized_roi_result.scalar() or 0.0

    return DashboardStats(
        total_whales_tracked=total_whales,
        high_signal_alerts_today=alerts_today,
        total_trades_monitored=total_trades,
        avg_insider_score=float(avg_score),
        total_resolved_trades=total_resolved,
        avg_win_rate=float(avg_win_rate),
        total_volume_24h=float(total_volume_24h),
        total_pnl_flagged=float(total_pnl_flagged),
        total_open_positions=total_open_positions,
        total_unrealized_pnl=float(total_unrealized_pnl),
        avg_unrealized_roi=float(avg_unrealized_roi)
    )


@router.get("/markets/watch", response_model=List[MarketWatchItem])
async def get_market_watch(
    category: Optional[str] = Query(None),
    sort_by: str = Query("suspicion_score", regex="^(suspicion_score|volatility_score|total_volume|suspicious_trades_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    limit: int = Query(50, le=200),
    session: AsyncSession = Depends(get_session)
):
    """
    Get markets sorted by suspicious activity or volatility.
    Filter by category (NBA, Politics, Crypto, etc.) if specified.
    """
    # Base query for active markets with metrics
    query = select(Market).where(Market.is_resolved == False)

    # Filter by category if specified
    if category:
        query = query.where(Market.category == category)

    # Sorting
    if sort_by == "suspicion_score":
        sort_col = Market.suspicion_score
    elif sort_by == "volatility_score":
        sort_col = Market.volatility_score
    elif sort_by == "total_volume":
        sort_col = Market.total_volume
    elif sort_by == "suspicious_trades_count":
        sort_col = Market.suspicious_trades_count
    else:
        sort_col = Market.suspicion_score

    if sort_order == "desc":
        query = query.order_by(desc(sort_col))
    else:
        query = query.order_by(asc(sort_col))

    query = query.limit(limit)

    result = await session.execute(query)
    markets = result.scalars().all()

    return [MarketWatchItem.model_validate(market) for market in markets]


@router.get("/markets/{market_id}/trades", response_model=List[TradeResponse])
async def get_market_trades(
    market_id: str,
    limit: int = Query(50, le=10000, description="Max trades to return (up to 10000 for all-time)"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    session: AsyncSession = Depends(get_session)
):
    """
    Get trade history for a specific market.
    Supports pagination for fetching all-time trade history.
    """
    offset = (page - 1) * limit

    result = await session.execute(
        select(Trade)
        .where(Trade.market_id == market_id)
        .order_by(desc(Trade.timestamp))
        .offset(offset)
        .limit(limit)
    )
    trades = result.scalars().all()

    return [TradeResponse.model_validate(trade) for trade in trades]


@router.get("/markets/{market_id}/trades/count")
async def get_market_trades_count(
    market_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Get total trade count for a market.
    """
    result = await session.execute(
        select(func.count(Trade.id)).where(Trade.market_id == market_id)
    )
    count = result.scalar() or 0
    return {"market_id": market_id, "total_trades": count}


# ============== Backtesting Endpoints ==============

@router.get("/backtesting/tracked-markets", response_model=List[TrackedMarketResponse])
async def get_tracked_markets(
    category: Optional[str] = Query(None),
    active_only: bool = Query(True),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session)
):
    """
    Get list of markets being tracked for backtesting snapshots.
    """
    query = select(TrackedMarket)

    if active_only:
        query = query.where(TrackedMarket.is_active == True)

    if category:
        query = query.where(TrackedMarket.category == category)

    query = query.order_by(desc(TrackedMarket.liquidity)).limit(limit)

    result = await session.execute(query)
    markets = result.scalars().all()

    return [TrackedMarketResponse.model_validate(m) for m in markets]


@router.post("/backtesting/track-market", response_model=TrackedMarketResponse)
async def add_tracked_market(
    market: TrackedMarketCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Add a market to the tracking list for backtesting data collection.
    """
    from app.services.snapshot_worker import get_snapshot_worker

    worker = await get_snapshot_worker()
    tracked = await worker.add_tracked_market(
        market_id=market.market_id,
        question=market.question,
        category=market.category,
        yes_token_id=market.yes_token_id,
        no_token_id=market.no_token_id,
    )

    return TrackedMarketResponse.model_validate(tracked)


@router.post("/backtesting/discover-markets", response_model=List[TrackedMarketResponse])
async def discover_markets(
    request: DiscoverMarketsRequest,
):
    """
    Auto-discover high-liquidity markets to track based on categories.
    Categories: 'politics', 'sports', 'crypto'
    """
    from app.services.snapshot_worker import get_snapshot_worker

    worker = await get_snapshot_worker()
    discovered = await worker.auto_discover_markets(
        categories=request.categories,
        min_liquidity=request.min_liquidity,
        min_volume=request.min_volume,
        limit=request.limit,
    )

    return [TrackedMarketResponse.model_validate(m) for m in discovered]


@router.delete("/backtesting/tracked-markets/{market_id}")
async def remove_tracked_market(
    market_id: str,
    session: AsyncSession = Depends(get_session)
):
    """
    Remove a market from tracking (sets is_active=False).
    """
    result = await session.execute(
        select(TrackedMarket).where(TrackedMarket.market_id == market_id)
    )
    market = result.scalar_one_or_none()

    if not market:
        raise HTTPException(status_code=404, detail="Tracked market not found")

    market.is_active = False
    await session.commit()

    return {"message": f"Market {market_id} removed from tracking"}


@router.get("/backtesting/snapshots", response_model=List[MarketSnapshotResponse])
async def get_market_snapshots(
    market_id: str = Query(..., description="Market condition_id"),
    start_time: Optional[datetime] = Query(None),
    end_time: Optional[datetime] = Query(None),
    limit: int = Query(1000, le=10000),
    session: AsyncSession = Depends(get_session)
):
    """
    Get order book snapshots for a market within a time range.
    Used for backtesting spread analysis.
    """
    query = select(MarketSnapshot).where(MarketSnapshot.market_id == market_id)

    if start_time:
        query = query.where(MarketSnapshot.timestamp >= start_time)
    if end_time:
        query = query.where(MarketSnapshot.timestamp <= end_time)

    query = query.order_by(MarketSnapshot.timestamp).limit(limit)

    result = await session.execute(query)
    snapshots = result.scalars().all()

    return [MarketSnapshotResponse.model_validate(s) for s in snapshots]


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
    """
    Get historical price data for a market.
    Used for backtesting price-based strategies.
    """
    query = select(PriceHistory).where(PriceHistory.market_id == market_id)

    if outcome:
        query = query.where(PriceHistory.outcome == outcome.upper())
    if start_time:
        query = query.where(PriceHistory.timestamp >= start_time)
    if end_time:
        query = query.where(PriceHistory.timestamp <= end_time)
    if interval:
        query = query.where(PriceHistory.interval == interval)

    query = query.order_by(PriceHistory.timestamp).limit(limit)

    result = await session.execute(query)
    history = result.scalars().all()

    return [PriceHistoryResponse.model_validate(h) for h in history]


@router.post("/backtesting/backfill")
async def backfill_price_history(
    request: BackfillRequest,
):
    """
    Backfill historical price data for a market from the CLOB API.
    Fetches and stores price history for backtesting.
    """
    from app.services.snapshot_worker import get_snapshot_worker

    worker = await get_snapshot_worker()
    count = await worker.backfill_price_history(
        market_id=request.market_id,
        token_id=request.token_id,
        outcome=request.outcome,
        interval=request.interval,
        fidelity=request.fidelity,
        days_back=request.days_back,
    )

    return {
        "message": f"Backfilled {count} price points",
        "market_id": request.market_id,
        "outcome": request.outcome,
        "days_back": request.days_back,
    }


@router.post("/backfill/trades")
async def backfill_trades(
    max_pages: int = Query(100, le=500, description="Maximum pages to fetch (500 trades/page)"),
    market_ids: Optional[List[str]] = Query(None, description="Optional list of market IDs to filter for"),
):
    """
    Backfill historical trades from Polymarket API.
    Paginates through trade history and stores all trades meeting minimum size requirements.
    """
    from app.services.data_worker import run_backfill

    # Convert to set for faster lookup if provided
    target_markets = set(market_ids) if market_ids else None

    # Run backfill (this could take a while)
    new_trades = await run_backfill(max_pages=max_pages)

    return {
        "message": f"Backfill complete",
        "new_trades_ingested": new_trades,
        "max_pages_requested": max_pages,
    }


@router.get("/backtesting/stats")
async def get_backtesting_stats(
    session: AsyncSession = Depends(get_session)
):
    """
    Get statistics about backtesting data collection.
    """
    # Count tracked markets
    tracked_result = await session.execute(
        select(func.count(TrackedMarket.id)).where(TrackedMarket.is_active == True)
    )
    tracked_count = tracked_result.scalar() or 0

    # Count total snapshots
    snapshot_result = await session.execute(
        select(func.count(MarketSnapshot.id))
    )
    snapshot_count = snapshot_result.scalar() or 0

    # Count price history points
    price_result = await session.execute(
        select(func.count(PriceHistory.id))
    )
    price_count = price_result.scalar() or 0

    # Get date range of data
    oldest_snapshot = await session.execute(
        select(func.min(MarketSnapshot.timestamp))
    )
    oldest_ts = oldest_snapshot.scalar()

    newest_snapshot = await session.execute(
        select(func.max(MarketSnapshot.timestamp))
    )
    newest_ts = newest_snapshot.scalar()

    return {
        "tracked_markets": tracked_count,
        "total_snapshots": snapshot_count,
        "total_price_points": price_count,
        "data_range": {
            "oldest": oldest_ts,
            "newest": newest_ts,
        }
    }
