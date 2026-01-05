import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional, List, Sequence

from app.models.database import Trade, TraderProfile
from app.config import get_settings


class InsiderDetector:
    def __init__(self, z_score_threshold: Optional[float] = None):
        settings = get_settings()
        self.z_score_threshold = z_score_threshold or settings.z_score_threshold

    async def calculate_z_score(
        self,
        wallet_address: str,
        trade_size: float,
        session: AsyncSession
    ) -> tuple[float, bool]:
        """
        Calculate Z-score for a trade based on wallet's historical average.
        Returns (z_score, is_anomaly)
        """
        # Get historical trades for this wallet
        result = await session.execute(
            select(Trade.trade_size_usd)
            .where(Trade.wallet_address == wallet_address)
            .order_by(Trade.timestamp.desc())
            .limit(100)
        )
        historical_trades = result.scalars().all()

        if len(historical_trades) < 3:
            # Not enough data, use a simple threshold
            return 0.0, trade_size > 10000

        trade_sizes = np.array(historical_trades)
        mean = np.mean(trade_sizes)
        std = np.std(trade_sizes)

        if std == 0:
            return 0.0, False

        z_score = (trade_size - mean) / std
        is_anomaly = abs(z_score) > self.z_score_threshold

        return float(z_score), is_anomaly

    async def update_trader_profile(
        self,
        wallet_address: str,
        session: AsyncSession
    ) -> Optional[TraderProfile]:
        """
        Update or create trader profile with latest statistics.
        """
        # Get all trades for this wallet
        trades_result = await session.execute(
            select(Trade)
            .where(Trade.wallet_address == wallet_address)
            .order_by(Trade.timestamp.desc())
        )
        trades = list(trades_result.scalars().all())

        if not trades:
            return None

        trade_sizes = [t.trade_size_usd for t in trades]
        flagged_trades = [t for t in trades if t.is_flagged]

        # Calculate statistics
        total_trades = len(trades)
        avg_bet_size = float(np.mean(trade_sizes))
        std_bet_size = float(np.std(trade_sizes)) if len(trade_sizes) > 1 else 0.0
        max_bet_size = float(np.max(trade_sizes))
        total_volume = float(np.sum(trade_sizes))
        flagged_count = len(flagged_trades)

        # Calculate insider score (0-100)
        # Based on: percentage of flagged trades, avg z-score of flagged trades, recency
        insider_score = self._calculate_insider_score(trades, flagged_trades)

        # Get or create profile
        profile_result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == wallet_address)
        )
        profile = profile_result.scalar_one_or_none()

        if profile:
            profile.total_trades = total_trades
            profile.avg_bet_size = float(avg_bet_size)
            profile.std_bet_size = float(std_bet_size)
            profile.max_bet_size = float(max_bet_size)
            profile.total_volume = float(total_volume)
            profile.insider_score = insider_score
            profile.flagged_trades_count = flagged_count
            profile.last_updated = datetime.utcnow()
        else:
            profile = TraderProfile(
                wallet_address=wallet_address,
                total_trades=total_trades,
                avg_bet_size=float(avg_bet_size),
                std_bet_size=float(std_bet_size),
                max_bet_size=float(max_bet_size),
                total_volume=float(total_volume),
                insider_score=insider_score,
                flagged_trades_count=flagged_count,
                last_updated=datetime.utcnow()
            )
            session.add(profile)

        await session.commit()
        await session.refresh(profile)
        return profile

    def _calculate_insider_score(self, all_trades: Sequence[Trade], flagged_trades: List[Trade]) -> float:
        """
        Calculate insider confidence score (0-100).
        Higher score = more suspicious activity.
        """
        if not all_trades:
            return 0.0

        # Component 1: Percentage of flagged trades (0-40 points)
        flagged_percentage = len(flagged_trades) / len(all_trades)
        score = flagged_percentage * 40

        # Component 2: Average Z-score of flagged trades (0-30 points)
        if flagged_trades:
            z_scores = [t.z_score for t in flagged_trades if t.z_score is not None]
            if z_scores:
                avg_z_score = float(np.mean(z_scores))
                # Normalize: z-score of 3 = 10 points, 6 = 20, 9+ = 30
                score += min(avg_z_score / 9 * 30, 30)

        # Component 3: Recency of flagged trades (0-30 points)
        recent_trades = [t for t in all_trades if
                        (datetime.utcnow() - t.timestamp).days <= 7]
        if recent_trades:
            recent_flagged = [t for t in recent_trades if t.is_flagged]
            recent_percentage = len(recent_flagged) / len(recent_trades)
            score += recent_percentage * 30

        return min(score, 100.0)

    async def get_trending_trades(
        self,
        session: AsyncSession,
        min_size: float = 5000,
        hours: int = 24
    ) -> Sequence[Trade]:
        """
        Get recent trades that are flagged or exceed minimum size.
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        result = await session.execute(
            select(Trade)
            .where(
                (Trade.timestamp >= cutoff_time) &
                ((Trade.is_flagged == True) | (Trade.trade_size_usd >= min_size))
            )
            .order_by(Trade.timestamp.desc())
            .limit(100)
        )

        return result.scalars().all()
