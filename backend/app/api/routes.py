from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, and_
from datetime import datetime, timedelta
from typing import List, Optional
from app.models.database import get_session, Trade, TraderProfile
from app.schemas.trader import (
    TraderProfileResponse,
    TraderListItem,
    TrendingTrade,
    DashboardStats,
    TradeResponse
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

    return DashboardStats(
        total_whales_tracked=total_whales,
        high_signal_alerts_today=alerts_today,
        total_trades_monitored=total_trades,
        avg_insider_score=float(avg_score),
        total_resolved_trades=total_resolved,
        avg_win_rate=float(avg_win_rate),
        total_volume_24h=float(total_volume_24h),
        total_pnl_flagged=float(total_pnl_flagged)
    )
