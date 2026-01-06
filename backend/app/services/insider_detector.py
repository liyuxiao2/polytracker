import numpy as np
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional, List, Tuple

from app.models.database import Trade, TraderProfile, Market
from app.config import get_settings


# Thresholds for insider detection - based on RELATIVE deviation, not absolute size
MIN_TRADES_FOR_WIN_RATE = 10  # Minimum resolved trades to calculate win rate
SUSPICIOUS_WIN_RATE = 0.60  # 60%+ win rate is suspicious
DEVIATION_THRESHOLD_PCT = 2.00  # 50% above average = suspicious deviation
Z_SCORE_THRESHOLD = 1.5  # Standard deviations for anomaly (backup metric)


class InsiderDetector:
    def __init__(self, z_score_threshold: Optional[float] = None):
        settings = get_settings()
        self.z_score_threshold = z_score_threshold or settings.z_score_threshold

    async def calculate_z_score(
        self,
        wallet_address: str,
        trade_size: float,
        session: AsyncSession
    ) -> Tuple[float, bool]:
        """
        Calculate Z-score for a trade based on wallet's historical average.
        Returns (z_score, is_deviation_anomaly)

        A trade is flagged if:
        - Z-score exceeds threshold (statistical anomaly), OR
        - Trade size is 50%+ above the trader's average (relative deviation)
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
            # Not enough data - can't calculate deviation, flag for review
            return 0.0, True

        trade_sizes = np.array(historical_trades)
        mean = np.mean(trade_sizes)
        std = np.std(trade_sizes)

        # Calculate deviation percentage from average
        deviation_pct = (trade_size - mean) / mean if mean > 0 else 0

        if std == 0:
            # No variance - flag if significantly above average
            is_anomaly = deviation_pct >= DEVIATION_THRESHOLD_PCT
            return deviation_pct, is_anomaly

        z_score = (trade_size - mean) / std

        # Flag as anomaly if:
        # 1. Z-score exceeds threshold (statistical outlier), OR
        # 2. Trade is 50%+ above their average (relative deviation)
        is_anomaly = abs(z_score) > self.z_score_threshold or deviation_pct >= DEVIATION_THRESHOLD_PCT

        return float(z_score), is_anomaly

    async def evaluate_trade_for_insider_activity(
        self,
        trade: Trade,
        session: AsyncSession
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate if a trade should be flagged as potential insider activity.

        Criteria for flagging (must WIN the trade):
        1. Bet size was 50%+ above their average AND they won
        2. Trader has suspicious win rate on resolved trades

        Returns (should_flag, reason)
        """
        # Skip if trade not resolved yet
        if not trade.is_resolved or trade.is_win is None:
            return False, None

        reasons = []

        # Get trader's average bet size for comparison
        avg_bet = await self._get_trader_avg_bet_size(trade.wallet_address, session)

        # Check 1: Deviation-based flag - bet was significantly above average AND WON
        if trade.is_win and avg_bet > 0:
            deviation_pct = (trade.trade_size_usd - avg_bet) / avg_bet
            if deviation_pct >= DEVIATION_THRESHOLD_PCT:
                reasons.append(f"Won with +{deviation_pct*100:.0f}% deviation from avg (${trade.trade_size_usd:.0f} vs avg ${avg_bet:.0f})")

        # Also check z-score if available
        if trade.is_win and trade.z_score and abs(trade.z_score) > self.z_score_threshold:
            reasons.append(f"Statistical anomaly won (z={trade.z_score:.1f})")

        # Check 2: Check trader's overall win rate
        win_rate, resolved_count = await self._get_trader_win_rate(trade.wallet_address, session)

        if resolved_count >= MIN_TRADES_FOR_WIN_RATE and win_rate >= SUSPICIOUS_WIN_RATE:
            reasons.append(f"Suspicious win rate: {win_rate*100:.0f}% on {resolved_count} trades")

        if reasons:
            return True, "; ".join(reasons)

        return False, None

    async def _get_trader_avg_bet_size(
        self,
        wallet_address: str,
        session: AsyncSession
    ) -> float:
        """Get trader's average bet size."""
        result = await session.execute(
            select(func.avg(Trade.trade_size_usd))
            .where(Trade.wallet_address == wallet_address)
        )
        avg = result.scalar()
        return float(avg) if avg else 0.0

    async def _get_trader_win_rate(
        self,
        wallet_address: str,
        session: AsyncSession
    ) -> Tuple[float, int]:
        """Get trader's win rate on resolved trades."""
        result = await session.execute(
            select(
                func.count(Trade.id).label("total"),
                func.sum(func.cast(Trade.is_win, type_=func.Integer)).label("wins")
            )
            .where(
                and_(
                    Trade.wallet_address == wallet_address,
                    Trade.is_resolved == True,
                    Trade.is_win.isnot(None)
                )
            )
        )
        row = result.one()
        total = row.total or 0
        wins = row.wins or 0

        if total == 0:
            return 0.0, 0

        return wins / total, total

    async def update_trader_profile(
        self,
        wallet_address: str,
        session: AsyncSession
    ) -> Optional[TraderProfile]:
        """
        Update or create trader profile with latest statistics including win rate.
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

        # Calculate stats
        trade_sizes = [t.trade_size_usd for t in trades]
        total_trades = len(trades)
        avg_bet_size = float(np.mean(trade_sizes))
        std_bet_size = float(np.std(trade_sizes)) if len(trade_sizes) > 1 else 0.0
        max_bet_size = float(np.max(trade_sizes))
        total_volume = float(np.sum(trade_sizes))

        # Win/loss stats
        resolved_trades = [t for t in trades if t.is_resolved and t.is_win is not None]
        resolved_count = len(resolved_trades)
        winning_trades = [t for t in resolved_trades if t.is_win]
        winning_count = len(winning_trades)
        win_rate = winning_count / resolved_count if resolved_count > 0 else 0.0

        # PnL
        total_pnl = sum(t.pnl_usd or 0 for t in trades)

        # Flagged trades
        flagged_trades = [t for t in trades if t.is_flagged]
        flagged_count = len(flagged_trades)
        flagged_wins = [t for t in flagged_trades if t.is_win]
        flagged_wins_count = len(flagged_wins)

        # Calculate insider score
        insider_score = self._calculate_insider_score(
            total_trades=total_trades,
            resolved_count=resolved_count,
            win_rate=win_rate,
            flagged_count=flagged_count,
            flagged_wins_count=flagged_wins_count,
            trades=trades
        )

        # Get or create profile
        profile_result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == wallet_address)
        )
        profile = profile_result.scalar_one_or_none()

        if profile:
            profile.total_trades = total_trades
            profile.resolved_trades = resolved_count
            profile.winning_trades = winning_count
            profile.win_rate = win_rate
            profile.avg_bet_size = avg_bet_size
            profile.std_bet_size = std_bet_size
            profile.max_bet_size = max_bet_size
            profile.total_volume = total_volume
            profile.total_pnl = total_pnl
            profile.insider_score = insider_score
            profile.flagged_trades_count = flagged_count
            profile.flagged_wins_count = flagged_wins_count
            profile.last_updated = datetime.utcnow()
        else:
            profile = TraderProfile(
                wallet_address=wallet_address,
                total_trades=total_trades,
                resolved_trades=resolved_count,
                winning_trades=winning_count,
                win_rate=win_rate,
                avg_bet_size=avg_bet_size,
                std_bet_size=std_bet_size,
                max_bet_size=max_bet_size,
                total_volume=total_volume,
                total_pnl=total_pnl,
                insider_score=insider_score,
                flagged_trades_count=flagged_count,
                flagged_wins_count=flagged_wins_count,
                last_updated=datetime.utcnow()
            )
            session.add(profile)

        return profile

    def _calculate_insider_score(
        self,
        total_trades: int,
        resolved_count: int,
        win_rate: float,
        flagged_count: int,
        flagged_wins_count: int,
        trades: List[Trade]
    ) -> float:
        """
        Calculate insider confidence score (0-100).
        Higher score = more suspicious.

        Components:
        - Win rate bonus (0-40): High win rate on enough resolved trades
        - Flagged wins ratio (0-35): % of flagged (anomalous) trades that won
        - Deviation wins (0-25): Trades 50%+ above avg that won
        """
        score = 0.0

        # Component 1: Win rate (0-40 points)
        # Only counts if they have enough resolved trades
        if resolved_count >= MIN_TRADES_FOR_WIN_RATE:
            if win_rate >= SUSPICIOUS_WIN_RATE:
                # Scale from 60% -> 10 points to 100% -> 40 points
                score += 10 + (win_rate - 0.6) * 75  # 60%=10, 80%=25, 100%=40
                score = min(score, 40)

        # Component 1b: Give some points just for having trades
        if total_trades >= 1:
            score += min(total_trades * 2, 15)  # Up to 15 points for activity

        # Component 2: Flagged trades that won (0-35 points)
        if flagged_count > 0:
            flagged_win_rate = flagged_wins_count / flagged_count
            score += flagged_win_rate * 35

        # Component 3: Deviation-based wins in recent history (0-25 points)
        # Count trades where bet was 50%+ above average AND won
        recent_trades = [t for t in trades if
                        t.timestamp and (datetime.utcnow() - t.timestamp).days <= 30]
        
        if recent_trades:
            avg_size = np.mean([t.trade_size_usd for t in trades]) if trades else 0
            if avg_size > 0:
                deviation_wins = [t for t in recent_trades if
                                 t.is_win and 
                                 (t.trade_size_usd - avg_size) / avg_size >= DEVIATION_THRESHOLD_PCT]
                deviation_win_ratio = len(deviation_wins) / len(recent_trades)
                score += deviation_win_ratio * 25

        return min(score, 100.0)

    async def get_trending_trades(
        self,
        session: AsyncSession,
        min_size: float = 5000,
        hours: int = 24
    ) -> List[Trade]:
        """
        Get recent trades that are flagged, have high z-scores, or are significant wins.
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        result = await session.execute(
            select(Trade)
            .where(
                and_(
                    Trade.timestamp >= cutoff_time,
                    (
                        (Trade.is_flagged == True) |
                        (Trade.trade_size_usd >= min_size) |
                        ((Trade.is_win == True) & (Trade.z_score >= Z_SCORE_THRESHOLD))
                    )
                )
            )
            .order_by(Trade.timestamp.desc())
            .limit(100)
        )

        return list(result.scalars().all())

    async def get_suspicious_traders(
        self,
        session: AsyncSession,
        min_score: float = 50.0
    ) -> List[TraderProfile]:
        """Get traders with high insider scores."""
        result = await session.execute(
            select(TraderProfile)
            .where(TraderProfile.insider_score >= min_score)
            .order_by(TraderProfile.insider_score.desc())
            .limit(50)
        )
        return list(result.scalars().all())
