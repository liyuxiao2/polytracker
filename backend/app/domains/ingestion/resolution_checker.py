import asyncio
import random
from datetime import datetime, timedelta
from sqlalchemy import select, distinct, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Trade, Market, async_session_maker
from app.services.polymarket_client import PolymarketClient
from app.services.insider_detector import InsiderDetector
from app.config import get_settings


class ResolutionChecker:
    """
    Background service that checks for resolved markets and updates
    trade outcomes (win/loss) accordingly.

    Runs periodically to:
    1. Find unresolved trades
    2. Check if their markets have resolved
    3. Update win/loss status and PnL
    4. Flag suspicious winning trades
    """

    def __init__(self):
        self.client = PolymarketClient()
        self.detector = InsiderDetector()
        self.check_interval = 300  # Check every 5 minutes
        self.is_running = False

    async def start(self):
        """Start the resolution checker loop."""
        self.is_running = True
        settings = get_settings()

        if settings.mock_mode:
            print("[ResolutionChecker] Starting in mock mode (simulated resolutions)")
            await self._start_mock_mode()
            return

        print("[ResolutionChecker] Starting resolution checker")

        while self.is_running:
            try:
                await self._check_resolutions()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                print(f"[ResolutionChecker] Error: {e}")
                await asyncio.sleep(60)

    async def stop(self):
        """Stop the resolution checker."""
        self.is_running = False
        await self.client.close()
        print("[ResolutionChecker] Stopped")

    async def _check_resolutions(self):
        """Check for resolved markets and update trades."""
        async with async_session_maker() as session:
            # Get unique market IDs with unresolved trades
            result = await session.execute(
                select(distinct(Trade.market_id))
                .where(Trade.is_resolved == False)
                .limit(50)
            )
            unresolved_market_ids = [row[0] for row in result.all()]

            if not unresolved_market_ids:
                return

            print(f"[ResolutionChecker] Checking {len(unresolved_market_ids)} markets for resolution")

            resolved_count = 0
            for market_id in unresolved_market_ids:
                try:
                    resolved = await self._check_market_resolution(market_id, session)
                    if resolved:
                        resolved_count += 1
                except Exception as e:
                    print(f"[ResolutionChecker] Error checking market {market_id}: {e}")

            if resolved_count > 0:
                await session.commit()
                print(f"[ResolutionChecker] Resolved {resolved_count} markets")

    async def _check_market_resolution(self, market_id: str, session: AsyncSession) -> bool:
        """
        Check if a market has resolved and update all trades.
        Returns True if market was resolved.
        """
        # Fetch market status from API
        market_data = await self.client.get_market_by_id(market_id)

        if not market_data:
            return False

        if not market_data.get("is_resolved"):
            return False

        resolved_outcome = market_data.get("resolved_outcome")
        if not resolved_outcome:
            return False

        print(f"[ResolutionChecker] Market resolved: {market_id} -> {resolved_outcome}")

        # Update or create market record
        await self._update_market_record(market_id, market_data, session)

        # Get all trades for this market
        trades_result = await session.execute(
            select(Trade)
            .where(
                and_(
                    Trade.market_id == market_id,
                    Trade.is_resolved == False
                )
            )
        )
        trades = list(trades_result.scalars().all())

        # Update each trade
        wallets_to_update = set()

        for trade in trades:
            # Determine if trade won
            # If they bought YES and it resolved YES, they won
            # If they bought NO and it resolved NO, they won
            trade_outcome = trade.outcome  # What they bet on (YES/NO)
            is_win = (trade_outcome == resolved_outcome)

            # Calculate PnL
            # If won: payout = size * (1 / price) - size = size * (1 - price) / price
            # Simplified: if won at price p, they paid p and got 1, so profit = (1-p) * shares
            # If lost: they lose their stake
            entry_price = trade.price or 0.5
            if is_win:
                # They paid entry_price per share, got $1 per share
                pnl = trade.trade_size_usd * (1 - entry_price) / entry_price if entry_price > 0 else 0
            else:
                # They lost their entire stake
                pnl = -trade.trade_size_usd

            # Update trade
            trade.is_resolved = True
            trade.resolved_outcome = resolved_outcome
            trade.is_win = is_win
            trade.pnl_usd = pnl

            # Check if this trade should be flagged
            should_flag, reason = await self.detector.evaluate_trade_for_insider_activity(trade, session)
            if should_flag:
                trade.is_flagged = True
                trade.flag_reason = reason
                print(f"[ResolutionChecker] Flagged trade: {trade.wallet_address[:10]}... - {reason}")

            wallets_to_update.add(trade.wallet_address)

        # Update trader profiles for affected wallets
        for wallet in wallets_to_update:
            await self.detector.update_trader_profile(wallet, session)

        return True

    async def _update_market_record(self, market_id: str, market_data: dict, session: AsyncSession):
        """Update or create market record."""
        result = await session.execute(
            select(Market).where(Market.market_id == market_id)
        )
        market = result.scalar_one_or_none()

        if market:
            market.is_resolved = True
            market.resolved_outcome = market_data.get("resolved_outcome")
            market.resolution_time = datetime.utcnow()
            market.last_checked = datetime.utcnow()
        else:
            market = Market(
                market_id=market_id,
                condition_id=market_data.get("condition_id"),
                question=market_data.get("question", "Unknown"),
                is_resolved=True,
                resolved_outcome=market_data.get("resolved_outcome"),
                resolution_time=datetime.utcnow(),
                last_checked=datetime.utcnow()
            )
            session.add(market)

    async def _start_mock_mode(self):
        """Run resolution checker in mock mode - simulates market resolutions."""
        while self.is_running:
            try:
                await self._mock_resolve_trades()
                await asyncio.sleep(30)  # Check every 30 seconds in mock mode
            except Exception as e:
                print(f"[ResolutionChecker] Mock mode error: {e}")
                await asyncio.sleep(10)

    async def _mock_resolve_trades(self):
        """Simulate market resolutions for mock trades."""
        async with async_session_maker() as session:
            # Get unresolved trades older than 30 seconds (simulate quick resolution)
            cutoff = datetime.utcnow() - timedelta(seconds=30)
            result = await session.execute(
                select(Trade)
                .where(
                    and_(
                        Trade.is_resolved == False,
                        Trade.timestamp <= cutoff
                    )
                )
                .limit(50)
            )
            unresolved_trades = list(result.scalars().all())

            if not unresolved_trades:
                return

            print(f"[ResolutionChecker] Mock resolving {len(unresolved_trades)} trades")

            wallets_to_update = set()

            for trade in unresolved_trades:
                # Simulate outcome - 50% win rate base, slightly higher for larger bets
                win_probability = 0.5
                if trade.trade_size_usd >= 500:
                    win_probability = 0.55  # Slightly better odds for larger bets
                if trade.trade_size_usd >= 1000:
                    win_probability = 0.60

                is_win = random.random() < win_probability
                resolved_outcome = trade.outcome if is_win else ("NO" if trade.outcome == "YES" else "YES")

                # Calculate PnL
                entry_price = trade.price or 0.5
                if is_win:
                    pnl = trade.trade_size_usd * (1 - entry_price) / entry_price if entry_price > 0 else 0
                else:
                    pnl = -trade.trade_size_usd

                # Update trade
                trade.is_resolved = True
                trade.resolved_outcome = resolved_outcome
                trade.is_win = is_win
                trade.pnl_usd = pnl

                # Check if this trade should be flagged as insider activity
                should_flag, reason = await self.detector.evaluate_trade_for_insider_activity(trade, session)
                if should_flag:
                    trade.is_flagged = True
                    trade.flag_reason = reason
                    print(f"[ResolutionChecker] Flagged: {trade.wallet_address[:10]}... - {reason}")

                wallets_to_update.add(trade.wallet_address)

            # Update trader profiles
            for wallet in wallets_to_update:
                await self.detector.update_trader_profile(wallet, session)

            await session.commit()
            print(f"[ResolutionChecker] Mock resolved {len(unresolved_trades)} trades, updated {len(wallets_to_update)} profiles")


# Global instance
_resolution_checker = None


async def get_resolution_checker() -> ResolutionChecker:
    global _resolution_checker
    if _resolution_checker is None:
        _resolution_checker = ResolutionChecker()
    return _resolution_checker
