import numpy as np
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict
from app.models.database import Trade, TraderProfile
import os


class InsiderDetector:
    """
    Advanced insider trading detection system.

    Detection signals implemented:
    1. Z-score anomaly (bet size vs wallet history)
    2. High conviction bets (low probability outcomes that win)
    3. Win rate on flagged/anomalous trades
    4. Market concentration (only trading 1-2 markets)
    5. Wallet age (new wallets making large bets)
    6. Timing before resolution (bets placed close to outcome)
    7. Off-hours trading (2-6 AM UTC activity)
    8. Longshot win rate (winning at < 20% odds)
    9. Large bet win rate (winning on outsized positions)
    10. Coordinated trading (multiple wallets, same market, tight window)
    """

    # Off-hours defined as 2-6 AM UTC (low liquidity, less scrutiny)
    OFF_HOURS_START = 2
    OFF_HOURS_END = 6

    def __init__(self, z_score_threshold: float = 3.0):
        self.z_score_threshold = float(os.getenv("Z_SCORE_THRESHOLD", z_score_threshold))

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

    async def evaluate_trade_for_insider_activity(
        self,
        trade: Trade,
        session: AsyncSession
    ) -> Tuple[bool, Optional[str]]:
        """
        Evaluate a resolved trade for insider activity indicators.
        Called after market resolution to flag suspicious winning trades.

        Returns (should_flag, reason)
        """
        reasons = []

        # Already flagged trades don't need re-evaluation
        if trade.is_flagged:
            return False, None

        # Only evaluate winning trades for post-resolution flagging
        if not trade.is_win:
            return False, None

        # Check 1: Large winning bet (> $10k profit)
        if trade.pnl_usd and trade.pnl_usd > 10000:
            reasons.append(f"Large winning bet: ${trade.pnl_usd:,.0f} profit")

        # Check 2: High conviction bet (bought at very low price, won)
        if trade.price and trade.price < 0.2:
            reasons.append(f"High conviction: bought at {trade.price:.0%} odds")

        # Check 3: Large bet relative to wallet's average
        profile_result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == trade.wallet_address)
        )
        profile = profile_result.scalar_one_or_none()

        if profile and profile.avg_bet_size > 0:
            deviation = (trade.trade_size_usd - profile.avg_bet_size) / profile.avg_bet_size
            if deviation > 2.0:  # More than 2x their average
                reasons.append(f"Bet {deviation:.1f}x larger than average")

        # Check 4: Check wallet's win rate on flagged trades
        if profile and profile.flagged_trades_count >= 3:
            # Get win rate on flagged trades
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
                if win_rate > 0.7:  # Suspiciously high win rate on flagged trades
                    reasons.append(f"High win rate on anomalous trades: {win_rate:.0%}")

        if reasons:
            return True, "; ".join(reasons)

        return False, None

    async def analyze_wallet_signals(
        self,
        wallet_address: str,
        session: AsyncSession
    ) -> Dict[str, any]:
        """
        Comprehensive analysis of a wallet's trading signals.
        Returns a dictionary of all computed signals for insider detection.
        """
        # Get all trades for this wallet
        result = await session.execute(
            select(Trade)
            .where(Trade.wallet_address == wallet_address)
            .order_by(Trade.timestamp.asc())
        )
        trades = list(result.scalars().all())

        if not trades:
            return {}

        signals = {}

        # 1. Wallet age and first seen
        first_trade = trades[0]
        last_trade = trades[-1]
        signals["first_seen"] = first_trade.timestamp
        signals["wallet_age_days"] = (datetime.utcnow() - first_trade.timestamp).days
        signals["days_since_last_trade"] = (datetime.utcnow() - last_trade.timestamp).days

        # 2. Market concentration (Herfindahl-Hirschman Index style)
        market_counts: Dict[str, int] = {}
        for t in trades:
            market_counts[t.market_id] = market_counts.get(t.market_id, 0) + 1

        signals["unique_markets_count"] = len(market_counts)
        total_trades = len(trades)

        if total_trades > 0:
            # HHI: sum of squared market shares
            concentration = sum((count / total_trades) ** 2 for count in market_counts.values())
            signals["market_concentration"] = concentration
        else:
            signals["market_concentration"] = 0.0

        # 3. Off-hours trading percentage
        off_hours_trades = [
            t for t in trades
            if t.timestamp.hour >= self.OFF_HOURS_START and t.timestamp.hour < self.OFF_HOURS_END
        ]
        signals["off_hours_trade_pct"] = len(off_hours_trades) / total_trades if total_trades > 0 else 0.0

        # 4. Average entry price
        prices = [t.price for t in trades if t.price is not None and t.price > 0]
        signals["avg_entry_price"] = float(np.mean(prices)) if prices else None

        # 5. Longshot win rate (bets at < 20% odds)
        longshot_trades = [t for t in trades if t.price and t.price < 0.2 and t.is_win is not None]
        if longshot_trades:
            longshot_wins = sum(1 for t in longshot_trades if t.is_win)
            signals["longshot_win_rate"] = longshot_wins / len(longshot_trades)
        else:
            signals["longshot_win_rate"] = 0.0

        # 6. Large bet win rate (bets > 2x average)
        trade_sizes = [t.trade_size_usd for t in trades]
        avg_size = np.mean(trade_sizes) if trade_sizes else 0
        large_trades = [t for t in trades if t.trade_size_usd > avg_size * 2 and t.is_win is not None]
        if large_trades:
            large_wins = sum(1 for t in large_trades if t.is_win)
            signals["large_bet_win_rate"] = large_wins / len(large_trades)
        else:
            signals["large_bet_win_rate"] = 0.0

        # 7. Timing before resolution (for resolved trades)
        resolved_trades = [t for t in trades if t.is_resolved and t.hours_before_resolution is not None]
        if resolved_trades:
            signals["avg_hours_before_resolution"] = np.mean([t.hours_before_resolution for t in resolved_trades])
        else:
            signals["avg_hours_before_resolution"] = None

        return signals

    def is_new_wallet_large_bet(
        self,
        wallet_age_days: int,
        trade_size_usd: float,
        threshold_days: int = 7,
        threshold_usd: float = 5000
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if this is a new wallet making a suspiciously large bet.
        Signal: Fresh wallets with big positions are suspicious.
        """
        if wallet_age_days <= threshold_days and trade_size_usd >= threshold_usd:
            return True, f"New wallet ({wallet_age_days}d old) with large bet (${trade_size_usd:,.0f})"
        return False, None

    def is_concentrated_trader(
        self,
        unique_markets: int,
        total_trades: int,
        market_concentration: float,
        min_trades: int = 5
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if trader only focuses on very few markets.
        Signal: Traders with inside info often only trade specific markets.
        """
        if total_trades < min_trades:
            return False, None

        # Very concentrated: only 1-2 markets with HHI > 0.5
        if unique_markets <= 2 and market_concentration > 0.5:
            return True, f"Highly concentrated: {unique_markets} markets, {market_concentration:.0%} HHI"
        return False, None

    def is_suspicious_timing(
        self,
        hours_before_resolution: float,
        threshold_hours: float = 24
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if trade was placed suspiciously close to market resolution.
        Signal: Bets placed 1-24 hours before resolution could indicate knowledge.
        """
        if hours_before_resolution is not None and 0 < hours_before_resolution <= threshold_hours:
            return True, f"Bet placed {hours_before_resolution:.1f}h before resolution"
        return False, None

    def is_off_hours_trader(
        self,
        off_hours_pct: float,
        threshold: float = 0.3
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if trader frequently trades during off-hours.
        Signal: Off-hours trading can indicate avoiding scrutiny.
        """
        if off_hours_pct >= threshold:
            return True, f"High off-hours activity: {off_hours_pct:.0%} of trades during 2-6 AM UTC"
        return False, None

    def is_longshot_winner(
        self,
        longshot_win_rate: float,
        min_longshot_trades: int = 3,
        threshold: float = 0.5
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if trader has abnormally high win rate on longshot bets.
        Signal: Consistently winning at < 20% odds suggests information advantage.
        """
        if longshot_win_rate >= threshold:
            return True, f"High longshot win rate: {longshot_win_rate:.0%} on <20% odds bets"
        return False, None

    async def update_trader_profile(
        self,
        wallet_address: str,
        session: AsyncSession
    ) -> TraderProfile:
        """
        Update or create trader profile with latest statistics.
        Includes win rate, PnL, outcome bias, buy/sell tracking, and advanced signals.
        """
        # Get all trades for this wallet (ordered by timestamp for age calculation)
        result = await session.execute(
            select(Trade)
            .where(Trade.wallet_address == wallet_address)
            .order_by(Trade.timestamp.asc())
        )
        trades = list(result.scalars().all())

        if not trades:
            return None

        trade_sizes = [t.trade_size_usd for t in trades]
        flagged_trades = [t for t in trades if t.is_flagged]
        resolved_trades = [t for t in trades if t.is_resolved]
        winning_trades = [t for t in trades if t.is_win]
        flagged_wins = [t for t in flagged_trades if t.is_win]

        # Calculate basic statistics
        total_trades = len(trades)
        avg_bet_size = float(np.mean(trade_sizes))
        std_bet_size = float(np.std(trade_sizes)) if len(trade_sizes) > 1 else 0.0
        max_bet_size = float(np.max(trade_sizes))
        total_volume = float(np.sum(trade_sizes))
        flagged_count = len(flagged_trades)

        # Calculate win rate and PnL
        resolved_count = len(resolved_trades)
        winning_count = len(winning_trades)
        win_rate = (winning_count / resolved_count * 100) if resolved_count > 0 else 0.0
        total_pnl = sum(t.pnl_usd for t in trades if t.pnl_usd is not None)
        flagged_wins_count = len(flagged_wins)

        # Calculate outcome bias (-1 to +1, where +1 means always YES)
        yes_bets = sum(1 for t in trades if t.outcome == "YES")
        no_bets = sum(1 for t in trades if t.outcome == "NO")
        total_outcome_bets = yes_bets + no_bets
        outcome_bias = ((yes_bets - no_bets) / total_outcome_bets) if total_outcome_bets > 0 else 0.0

        # Calculate buy/sell counts
        total_buys = sum(1 for t in trades if t.side and t.side.upper() == "BUY")
        total_sells = sum(1 for t in trades if t.side and t.side.upper() == "SELL")

        # NEW: Calculate advanced signals
        first_trade = trades[0]
        last_trade = trades[-1]
        first_seen = first_trade.timestamp
        wallet_age_days = (datetime.utcnow() - first_seen).days
        days_since_last_trade = (datetime.utcnow() - last_trade.timestamp).days

        # Market concentration (HHI)
        market_counts: Dict[str, int] = {}
        for t in trades:
            market_counts[t.market_id] = market_counts.get(t.market_id, 0) + 1
        unique_markets_count = len(market_counts)
        market_concentration = sum((c / total_trades) ** 2 for c in market_counts.values()) if total_trades > 0 else 0.0

        # Off-hours trading percentage
        off_hours_trades = [
            t for t in trades
            if t.timestamp.hour >= self.OFF_HOURS_START and t.timestamp.hour < self.OFF_HOURS_END
        ]
        off_hours_trade_pct = len(off_hours_trades) / total_trades if total_trades > 0 else 0.0

        # Average entry price
        prices = [t.price for t in trades if t.price is not None and t.price > 0]
        avg_entry_price = float(np.mean(prices)) if prices else None

        # Longshot win rate (bets at < 20% odds)
        longshot_trades = [t for t in trades if t.price and t.price < 0.2 and t.is_win is not None]
        longshot_win_rate = (sum(1 for t in longshot_trades if t.is_win) / len(longshot_trades)) if longshot_trades else 0.0

        # Large bet win rate (bets > 2x average)
        large_trades = [t for t in trades if t.trade_size_usd > avg_bet_size * 2 and t.is_win is not None]
        large_bet_win_rate = (sum(1 for t in large_trades if t.is_win) / len(large_trades)) if large_trades else 0.0

        # Avg hours before resolution
        resolved_with_timing = [t for t in resolved_trades if t.hours_before_resolution is not None]
        avg_hours_before_resolution = float(np.mean([t.hours_before_resolution for t in resolved_with_timing])) if resolved_with_timing else None

        # Calculate insider score with all components
        insider_score = self._calculate_insider_score_v2(
            trades=trades,
            flagged_trades=flagged_trades,
            flagged_wins=flagged_wins,
            win_rate=win_rate,
            outcome_bias=outcome_bias,
            wallet_age_days=wallet_age_days,
            market_concentration=market_concentration,
            off_hours_trade_pct=off_hours_trade_pct,
            longshot_win_rate=longshot_win_rate,
            large_bet_win_rate=large_bet_win_rate
        )

        # Get or create profile
        result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == wallet_address)
        )
        profile = result.scalar_one_or_none()

        profile_data = {
            "total_trades": total_trades,
            "resolved_trades": resolved_count,
            "winning_trades": winning_count,
            "win_rate": win_rate,
            "avg_bet_size": avg_bet_size,
            "std_bet_size": std_bet_size,
            "max_bet_size": max_bet_size,
            "total_volume": total_volume,
            "total_pnl": total_pnl,
            "insider_score": insider_score,
            "flagged_trades_count": flagged_count,
            "flagged_wins_count": flagged_wins_count,
            "total_yes_bets": yes_bets,
            "total_no_bets": no_bets,
            "outcome_bias": outcome_bias,
            "total_buys": total_buys,
            "total_sells": total_sells,
            "last_updated": datetime.utcnow(),
            # New advanced fields
            "first_seen": first_seen,
            "wallet_age_days": wallet_age_days,
            "unique_markets_count": unique_markets_count,
            "market_concentration": market_concentration,
            "avg_hours_before_resolution": avg_hours_before_resolution,
            "off_hours_trade_pct": off_hours_trade_pct,
            "days_since_last_trade": days_since_last_trade,
            "avg_entry_price": avg_entry_price,
            "longshot_win_rate": longshot_win_rate,
            "large_bet_win_rate": large_bet_win_rate,
        }

        if profile:
            for key, value in profile_data.items():
                setattr(profile, key, value)
        else:
            profile = TraderProfile(wallet_address=wallet_address, **profile_data)
            session.add(profile)

        await session.commit()
        await session.refresh(profile)
        return profile

    def _calculate_insider_score(
        self,
        all_trades: list,
        flagged_trades: list,
        flagged_wins: list,
        win_rate: float,
        outcome_bias: float
    ) -> float:
        """
        Calculate insider confidence score (0-100).
        Higher score = more suspicious activity.

        Components:
        1. Percentage of flagged trades (0-25 points)
        2. Average Z-score of flagged trades (0-20 points)
        3. Recency of flagged trades (0-20 points)
        4. Win rate on flagged trades (0-20 points) - NEW
        5. Extreme outcome bias (0-15 points) - NEW
        """
        if not all_trades:
            return 0.0

        score = 0.0

        # Component 1: Percentage of flagged trades (0-25 points)
        flagged_percentage = len(flagged_trades) / len(all_trades)
        score += flagged_percentage * 25

        # Component 2: Average Z-score of flagged trades (0-20 points)
        if flagged_trades:
            z_scores = [abs(t.z_score) for t in flagged_trades if t.z_score is not None]
            if z_scores:
                avg_z_score = np.mean(z_scores)
                # Normalize: z-score of 3 = 6.7 points, 6 = 13.3, 9+ = 20
                score += min(avg_z_score / 9 * 20, 20)

        # Component 3: Recency of flagged trades (0-20 points)
        recent_trades = [t for t in all_trades if
                        (datetime.utcnow() - t.timestamp).days <= 7]
        if recent_trades:
            recent_flagged = [t for t in recent_trades if t.is_flagged]
            recent_percentage = len(recent_flagged) / len(recent_trades)
            score += recent_percentage * 20

        # Component 4: Win rate on flagged trades (0-20 points)
        # High win rate on anomalous trades is very suspicious
        if flagged_trades:
            resolved_flagged = [t for t in flagged_trades if t.is_win is not None]
            if len(resolved_flagged) >= 3:  # Need minimum sample
                flagged_win_rate = len(flagged_wins) / len(resolved_flagged)
                # 50% is baseline, 100% gets full points
                if flagged_win_rate > 0.5:
                    score += (flagged_win_rate - 0.5) * 40  # Max 20 points at 100% win rate

        # Component 5: Extreme outcome bias (0-15 points)
        # Traders who always bet one direction might have information
        bias_magnitude = abs(outcome_bias)
        if bias_magnitude > 0.7:  # More than 85% one direction
            score += (bias_magnitude - 0.7) * 50  # Max 15 points at 100% one direction

        return min(score, 100.0)

    def _calculate_insider_score_v2(
        self,
        trades: list,
        flagged_trades: list,
        flagged_wins: list,
        win_rate: float,
        outcome_bias: float,
        wallet_age_days: int,
        market_concentration: float,
        off_hours_trade_pct: float,
        longshot_win_rate: float,
        large_bet_win_rate: float
    ) -> float:
        """
        Enhanced insider confidence score (0-100).
        Higher score = more suspicious activity.

        Components (total 100 points):
        1. Percentage of flagged trades (0-15 points)
        2. Average Z-score of flagged trades (0-10 points)
        3. Recency of flagged trades (0-10 points)
        4. Win rate on flagged trades (0-15 points)
        5. Market concentration (0-10 points) - NEW
        6. New wallet + large bets (0-10 points) - NEW
        7. Off-hours trading (0-5 points) - NEW
        8. Longshot win rate (0-15 points) - NEW
        9. Large bet win rate (0-10 points) - NEW
        """
        if not trades:
            return 0.0

        score = 0.0
        total_trades = len(trades)

        # Component 1: Percentage of flagged trades (0-15 points)
        if total_trades > 0:
            flagged_percentage = len(flagged_trades) / total_trades
            score += flagged_percentage * 15

        # Component 2: Average Z-score of flagged trades (0-10 points)
        if flagged_trades:
            z_scores = [abs(t.z_score) for t in flagged_trades if t.z_score is not None]
            if z_scores:
                avg_z_score = np.mean(z_scores)
                # Normalize: z-score of 3 = 3.3 points, 6 = 6.7, 9+ = 10
                score += min(avg_z_score / 9 * 10, 10)

        # Component 3: Recency of flagged trades (0-10 points)
        recent_trades = [t for t in trades if (datetime.utcnow() - t.timestamp).days <= 7]
        if recent_trades:
            recent_flagged = [t for t in recent_trades if t.is_flagged]
            recent_percentage = len(recent_flagged) / len(recent_trades)
            score += recent_percentage * 10

        # Component 4: Win rate on flagged trades (0-15 points)
        if flagged_trades:
            resolved_flagged = [t for t in flagged_trades if t.is_win is not None]
            if len(resolved_flagged) >= 3:
                flagged_win_rate = len(flagged_wins) / len(resolved_flagged)
                # 50% is baseline, 100% gets full points
                if flagged_win_rate > 0.5:
                    score += (flagged_win_rate - 0.5) * 30  # Max 15 points at 100%

        # Component 5: Market concentration (0-10 points) - NEW
        # High concentration (HHI > 0.5) with enough trades is suspicious
        if total_trades >= 5 and market_concentration > 0.5:
            # Scale: 0.5 HHI = 0 points, 1.0 HHI = 10 points
            score += (market_concentration - 0.5) * 20

        # Component 6: New wallet with activity (0-10 points) - NEW
        # New wallets (< 7 days) with significant activity are suspicious
        if wallet_age_days <= 7 and total_trades >= 3:
            score += 10
        elif wallet_age_days <= 14 and total_trades >= 5:
            score += 5

        # Component 7: Off-hours trading (0-5 points) - NEW
        # Frequent off-hours trading (> 30%) is mildly suspicious
        if off_hours_trade_pct > 0.3:
            score += min((off_hours_trade_pct - 0.3) * 16.67, 5)  # Max 5 points

        # Component 8: Longshot win rate (0-15 points) - NEW
        # High win rate on < 20% odds bets is very suspicious
        longshot_trades = [t for t in trades if t.price and t.price < 0.2 and t.is_win is not None]
        if len(longshot_trades) >= 3:
            if longshot_win_rate > 0.3:  # Better than 30% on longshots
                score += min((longshot_win_rate - 0.3) * 21.4, 15)  # Max 15 points

        # Component 9: Large bet win rate (0-10 points) - NEW
        # High win rate on outsized bets is suspicious
        avg_bet = np.mean([t.trade_size_usd for t in trades]) if trades else 0
        large_trades = [t for t in trades if t.trade_size_usd > avg_bet * 2 and t.is_win is not None]
        if len(large_trades) >= 3:
            if large_bet_win_rate > 0.5:  # Better than 50% on large bets
                score += min((large_bet_win_rate - 0.5) * 20, 10)  # Max 10 points

        return min(score, 100.0)

    async def get_trending_trades(
        self,
        session: AsyncSession,
        min_size: float = 5000,
        hours: int = 24
    ) -> list:
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

    async def detect_coordinated_trading(
        self,
        market_id: str,
        session: AsyncSession,
        window_seconds: int = 300
    ) -> list:
        """
        Detect potential coordinated trading activity.
        Returns wallets that traded the same market within a short window.
        """
        # Get recent trades for this market
        result = await session.execute(
            select(Trade)
            .where(Trade.market_id == market_id)
            .order_by(Trade.timestamp.desc())
            .limit(100)
        )
        trades = result.scalars().all()

        if len(trades) < 2:
            return []

        # Group trades by time windows
        coordinated_groups = []
        for i, trade in enumerate(trades):
            window_start = trade.timestamp - timedelta(seconds=window_seconds)
            window_end = trade.timestamp + timedelta(seconds=window_seconds)

            # Find other trades in this window
            window_trades = [
                t for t in trades
                if t.id != trade.id
                and window_start <= t.timestamp <= window_end
                and t.wallet_address != trade.wallet_address
            ]

            if len(window_trades) >= 2:  # 3+ wallets trading together
                wallets = {trade.wallet_address} | {t.wallet_address for t in window_trades}
                coordinated_groups.append({
                    "market_id": market_id,
                    "wallets": list(wallets),
                    "trade_count": len(wallets),
                    "window_start": window_start,
                    "window_end": window_end
                })

        return coordinated_groups
