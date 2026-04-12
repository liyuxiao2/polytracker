"""Trader profile update and aggregation logic."""
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Dict
from app.core.database import Trade, TraderProfile
from app.core.config import get_settings
from app.domains.ingestion.scoring_engine import ScoringEngine


class ProfileUpdater:
    def __init__(self):
        self.settings = get_settings()
        self.scoring = ScoringEngine()

    async def update_trader_profile(
        self,
        wallet_address: str,
        session: AsyncSession,
        tracked_markets: set = None
    ) -> TraderProfile:
        """Update or create trader profile with latest statistics.
        Only includes trades from tracked markets if specified."""
        query = (
            select(Trade)
            .where(Trade.wallet_address == wallet_address)
            .order_by(Trade.timestamp.asc())
        )

        # Filter by tracked markets if provided
        if tracked_markets:
            query = query.where(Trade.market_id.in_(tracked_markets))

        result = await session.execute(query)
        trades = list(result.scalars().all())

        if not trades:
            return None

        trade_sizes = [t.trade_size_usd for t in trades]
        flagged_trades = [t for t in trades if t.is_flagged]
        resolved_trades = [t for t in trades if t.is_resolved]
        winning_trades = [t for t in trades if t.is_win]
        flagged_wins = [t for t in flagged_trades if t.is_win]

        total_trades = len(trades)
        avg_bet_size = float(np.mean(trade_sizes))
        std_bet_size = float(np.std(trade_sizes)) if len(trade_sizes) > 1 else 0.0
        max_bet_size = float(np.max(trade_sizes))
        total_volume = float(np.sum(trade_sizes))
        flagged_count = len(flagged_trades)

        resolved_count = len(resolved_trades)
        winning_count = len(winning_trades)
        win_rate = (winning_count / resolved_count * 100) if resolved_count > 0 else 0.0
        total_pnl = sum(t.pnl_usd for t in trades if t.pnl_usd is not None)
        flagged_wins_count = len(flagged_wins)

        yes_bets = sum(1 for t in trades if t.outcome == "YES")
        no_bets = sum(1 for t in trades if t.outcome == "NO")
        total_outcome_bets = yes_bets + no_bets
        outcome_bias = ((yes_bets - no_bets) / total_outcome_bets) if total_outcome_bets > 0 else 0.0

        total_buys = sum(1 for t in trades if t.side and t.side.upper() == "BUY")
        total_sells = sum(1 for t in trades if t.side and t.side.upper() == "SELL")

        # Advanced signals
        first_trade = trades[0]
        last_trade = trades[-1]
        first_seen = first_trade.timestamp
        wallet_age_days = (datetime.utcnow() - first_seen).days
        days_since_last_trade = (datetime.utcnow() - last_trade.timestamp).days

        market_counts: Dict[str, int] = {}
        for t in trades:
            market_counts[t.market_id] = market_counts.get(t.market_id, 0) + 1
        unique_markets_count = len(market_counts)
        market_concentration = sum((c / total_trades) ** 2 for c in market_counts.values()) if total_trades > 0 else 0.0

        off_hours_trades = [
            t for t in trades
            if t.timestamp.hour >= self.settings.off_hours_start and t.timestamp.hour < self.settings.off_hours_end
        ]
        off_hours_trade_pct = len(off_hours_trades) / total_trades if total_trades > 0 else 0.0

        prices = [t.price for t in trades if t.price is not None and t.price > 0]
        avg_entry_price = float(np.mean(prices)) if prices else None

        longshot_trades = [t for t in trades if t.price and t.price < 0.1 and t.is_win is not None]
        longshot_win_rate = (sum(1 for t in longshot_trades if t.is_win) / len(longshot_trades)) if longshot_trades else 0.0

        large_trades = [t for t in trades if t.trade_size_usd > avg_bet_size * self.settings.avg_bet_deviation_multiplier and t.is_win is not None]
        large_bet_win_rate = (sum(1 for t in large_trades if t.is_win) / len(large_trades)) if large_trades else 0.0

        resolved_with_timing = [t for t in resolved_trades if t.hours_before_resolution is not None]
        avg_hours_before_resolution = float(np.mean([t.hours_before_resolution for t in resolved_with_timing])) if resolved_with_timing else None

        # Unrealized P&L metrics
        open_positions = [t for t in trades if t.is_win is None and t.unrealized_pnl_usd is not None]
        open_positions_count = len(open_positions)
        total_unrealized_pnl = sum(t.unrealized_pnl_usd for t in open_positions) if open_positions else 0.0
        avg_unrealized_pnl = (total_unrealized_pnl / open_positions_count) if open_positions_count > 0 else 0.0
        open_capital = sum(t.trade_size_usd for t in open_positions) if open_positions else 0.0
        unrealized_roi = (total_unrealized_pnl / open_capital * 100) if open_capital > 0 else 0.0
        unrealized_win_count = sum(1 for t in open_positions if t.unrealized_pnl_usd > 0)
        unrealized_win_rate = (unrealized_win_count / open_positions_count * 100) if open_positions_count > 0 else 0.0

        profit_factor = self.scoring.calculate_profit_factor(trades)

        insider_score = self.scoring.calculate_insider_score_v3(
            trades=trades,
            flagged_trades=flagged_trades,
            win_rate=win_rate,
            wallet_age_days=wallet_age_days,
            market_concentration=market_concentration,
            off_hours_trade_pct=off_hours_trade_pct,
            longshot_win_rate=longshot_win_rate,
            large_bet_win_rate=large_bet_win_rate,
            profit_factor=profit_factor,
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
            "roi": self.scoring.calculate_roi(total_pnl, total_volume),
            "profit_factor": profit_factor,
            "open_positions_count": open_positions_count,
            "total_unrealized_pnl": total_unrealized_pnl,
            "avg_unrealized_pnl": avg_unrealized_pnl,
            "unrealized_roi": unrealized_roi,
            "unrealized_win_count": unrealized_win_count,
            "unrealized_win_rate": unrealized_win_rate,
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
