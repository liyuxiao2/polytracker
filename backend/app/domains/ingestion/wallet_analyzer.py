"""Wallet signal analysis for insider detection."""
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional, Tuple, Dict
from app.core.database import Trade, TraderProfile
from app.core.config import get_settings


class WalletAnalyzer:
    def __init__(self):
        self.settings = get_settings()

    async def evaluate_trade_for_insider_activity(
        self,
        trade: Trade,
        session: AsyncSession
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate a resolved trade for insider activity indicators.
        Returns (should_flag, reason)
        """
        reasons = []

        if trade.is_flagged:
            return False, None

        if not trade.is_win:
            return False, None

        if trade.pnl_usd and trade.pnl_usd > self.settings.profit_threshold:
            reasons.append(f"Large winning bet: ${trade.pnl_usd:,.0f} profit")

        if trade.price and trade.price < self.settings.odds_threshold:
            reasons.append(f"High conviction: bought at {trade.price:.0%} odds")

        profile_result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == trade.wallet_address)
        )
        profile = profile_result.scalar_one_or_none()

        if profile and profile.avg_bet_size > 0:
            deviation = (trade.trade_size_usd - profile.avg_bet_size) / profile.avg_bet_size
            if deviation > self.settings.avg_bet_deviation_multiplier:
                reasons.append(f"Bet {deviation:.1f}x larger than average")

        if profile and profile.flagged_trades_count >= self.settings.min_flagged_trades:
            flagged_result = await session.execute(
                select(Trade)
                .where(
                    (Trade.wallet_address == trade.wallet_address) &
                    (Trade.is_flagged == True) &
                    (Trade.is_win.isnot(None))
                )
            )
            flagged_trades = flagged_result.scalars().all()
            if flagged_trades:
                wins = sum(1 for t in flagged_trades if t.is_win)
                win_rate = wins / len(flagged_trades)
                if win_rate > 0.7:
                    reasons.append(f"High win rate on anomalous trades: {win_rate:.0%}")

        if reasons:
            return True, "; ".join(reasons)

        return False, None

    async def analyze_wallet_signals(
        self,
        wallet_address: str,
        session: AsyncSession
    ) -> Dict[str, any]:
        """Comprehensive analysis of a wallet's trading signals."""
        result = await session.execute(
            select(Trade)
            .where(Trade.wallet_address == wallet_address)
            .order_by(Trade.timestamp.asc())
        )
        trades = list(result.scalars().all())

        if not trades:
            return {}

        signals = {}

        first_trade = trades[0]
        last_trade = trades[-1]
        signals["first_seen"] = first_trade.timestamp
        signals["wallet_age_days"] = (datetime.utcnow() - first_trade.timestamp).days
        signals["days_since_last_trade"] = (datetime.utcnow() - last_trade.timestamp).days

        market_counts: Dict[str, int] = {}
        for t in trades:
            market_counts[t.market_id] = market_counts.get(t.market_id, 0) + 1

        signals["unique_markets_count"] = len(market_counts)
        total_trades = len(trades)

        if total_trades > 0:
            concentration = sum((count / total_trades) ** 2 for count in market_counts.values())
            signals["market_concentration"] = concentration
        else:
            signals["market_concentration"] = 0.0

        off_hours_trades = [
            t for t in trades
            if t.timestamp.hour >= self.settings.off_hours_start and t.timestamp.hour < self.settings.off_hours_end
        ]
        signals["off_hours_trade_pct"] = len(off_hours_trades) / total_trades if total_trades > 0 else 0.0

        prices = [t.price for t in trades if t.price is not None and t.price > 0]
        signals["avg_entry_price"] = float(np.mean(prices)) if prices else None

        longshot_trades = [t for t in trades if t.price and t.price < 0.1 and t.is_win is not None]
        if longshot_trades:
            longshot_wins = sum(1 for t in longshot_trades if t.is_win)
            signals["longshot_win_rate"] = longshot_wins / len(longshot_trades)
        else:
            signals["longshot_win_rate"] = 0.0

        trade_sizes = [t.trade_size_usd for t in trades]
        avg_size = np.mean(trade_sizes) if trade_sizes else 0
        large_trades = [t for t in trades if t.trade_size_usd > avg_size * self.settings.avg_bet_deviation_multiplier and t.is_win is not None]
        if large_trades:
            large_wins = sum(1 for t in large_trades if t.is_win)
            signals["large_bet_win_rate"] = large_wins / len(large_trades)
        else:
            signals["large_bet_win_rate"] = 0.0

        resolved_trades = [t for t in trades if t.is_resolved and t.hours_before_resolution is not None]
        if resolved_trades:
            signals["avg_hours_before_resolution"] = np.mean([t.hours_before_resolution for t in resolved_trades])
        else:
            signals["avg_hours_before_resolution"] = None

        return signals

    def is_new_wallet_large_bet(
        self, wallet_age_days: int, trade_size_usd: float,
        threshold_days: int = 7, threshold_usd: float = 10000
    ) -> Tuple[bool, Optional[str]]:
        """Check if this is a new wallet making a suspiciously large bet."""
        if wallet_age_days <= threshold_days and trade_size_usd >= threshold_usd:
            return True, f"New wallet ({wallet_age_days}d old) with large bet (${trade_size_usd:,.0f})"
        return False, None

    def is_concentrated_trader(
        self, unique_markets: int, total_trades: int,
        market_concentration: float, min_trades: int = 10
    ) -> Tuple[bool, Optional[str]]:
        """Check if trader only focuses on very few markets."""
        if total_trades < min_trades:
            return False, None
        if unique_markets <= 2 and market_concentration > self.settings.market_concentration_threshold:
            return True, f"Highly concentrated: {unique_markets} markets, {market_concentration:.0%} HHI"
        return False, None

    def is_suspicious_timing(
        self, hours_before_resolution: float, threshold_hours: float = None
    ) -> Tuple[bool, Optional[str]]:
        """Check if trade was placed suspiciously close to market resolution."""
        if threshold_hours is None:
            threshold_hours = self.settings.pre_resolution_hours
        if hours_before_resolution is not None and 0 < hours_before_resolution <= threshold_hours:
            return True, f"Bet placed {hours_before_resolution:.1f}h before resolution"
        return False, None

    def is_off_hours_trader(
        self, off_hours_pct: float, threshold: float = 0.5
    ) -> Tuple[bool, Optional[str]]:
        """Check if trader frequently trades during off-hours."""
        if off_hours_pct >= threshold:
            return True, f"High off-hours activity: {off_hours_pct:.0%} of trades during 2-6 AM UTC"
        return False, None

    def is_longshot_winner(
        self, longshot_win_rate: float, min_longshot_trades: int = 5, threshold: float = None
    ) -> Tuple[bool, Optional[str]]:
        """Check if trader has abnormally high win rate on longshot bets."""
        if threshold is None:
            threshold = self.settings.longshot_win_rate_high
        if longshot_win_rate >= threshold:
            return True, f"High longshot win rate: {longshot_win_rate:.0%} on <10% odds bets"
        return False, None
