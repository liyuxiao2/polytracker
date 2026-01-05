from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from datetime import datetime, timedelta
from typing import List

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
            flagged_trades_count=profile.flagged_trades_count,
            last_trade_time=last_trade
        ))

    return traders_list


@router.get("/trades/trending", response_model=List[TrendingTrade])
async def get_trending_trades(
    min_size: float = Query(5000, ge=0),
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(100, le=500),
    session: AsyncSession = Depends(get_session)
):
    """
    Get real-time stream of trades filtered by size or high deviation.
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    result = await session.execute(
        select(Trade)
        .where(
            (Trade.timestamp >= cutoff_time) &
            ((Trade.is_flagged == True) | (Trade.trade_size_usd >= min_size))
        )
        .order_by(desc(Trade.timestamp))
        .limit(limit)
    )
    trades = result.scalars().all()

    # Get trader profiles to calculate deviation percentage
    trending = []
    for trade in trades:
        profile_result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == trade.wallet_address)
        )
        profile = profile_result.scalar_one_or_none()

        if profile and profile.avg_bet_size > 0:
            deviation_pct = ((trade.trade_size_usd - profile.avg_bet_size) / profile.avg_bet_size) * 100
        else:
            deviation_pct = 0.0

        trending.append(TrendingTrade(
            wallet_address=trade.wallet_address,
            market_name=trade.market_name,
            trade_size_usd=trade.trade_size_usd,
            z_score=trade.z_score or 0.0,
            timestamp=trade.timestamp,
            deviation_percentage=deviation_pct
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

    return DashboardStats(
        total_whales_tracked=total_whales,
        high_signal_alerts_today=alerts_today,
        total_trades_monitored=total_trades,
        avg_insider_score=float(avg_score)
    )
