import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.database import Trade, TraderProfile, async_session_maker
from app.services.polymarket_client import PolymarketClient
import os


class TradeResolutionWorker:
    """
    Background worker that checks unresolved trades and updates their win/loss status
    by querying Polymarket API for market resolution data.
    """

    def __init__(self):
        self.client = PolymarketClient()
        self.poll_interval = int(os.getenv("RESOLUTION_POLL_INTERVAL", "300"))  # 5 min default
        self.is_running = False
        self._market_cache: Dict[str, dict] = {}  # Cache market resolution status
        self._cache_ttl = 60  # Cache TTL in seconds

    async def start(self):
        """
        Start the background worker that checks trade resolutions.
        """
        self.is_running = True
        print(f"[ResolutionWorker] Starting trade resolution worker (poll interval: {self.poll_interval}s)")

        while self.is_running:
            try:
                await self._check_resolutions()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                print(f"[ResolutionWorker] Error in resolution loop: {e}")
                await asyncio.sleep(30)  # Brief pause on error

    async def stop(self):
        """
        Stop the background worker.
        """
        self.is_running = False
        await self.client.close()
        print("[ResolutionWorker] Trade resolution worker stopped")

    async def _check_resolutions(self):
        """
        Find unresolved trades and check if their markets have resolved.
        Phase 1: Update unrealized P&L on open positions
        Phase 2: Check for resolutions
        """
        # Phase 1: Update unrealized P&L for open positions
        await self._update_unrealized_pnl()

        # Phase 2: Check for resolutions (existing logic)
        async with async_session_maker() as session:
            # Get unresolved trades (is_win is NULL)
            result = await session.execute(
                select(Trade)
                .where(Trade.is_win.is_(None))
                .order_by(Trade.timestamp.desc())
                .limit(500)  # Process in batches
            )
            unresolved_trades = result.scalars().all()

            if not unresolved_trades:
                print("[ResolutionWorker] No unresolved trades to check")
                return

            print(f"[ResolutionWorker] Checking {len(unresolved_trades)} unresolved trades")

            # Group trades by market_id to minimize API calls
            trades_by_market: Dict[str, List[Trade]] = {}
            for trade in unresolved_trades:
                if trade.market_id not in trades_by_market:
                    trades_by_market[trade.market_id] = []
                trades_by_market[trade.market_id].append(trade)

            resolved_count = 0
            for market_id, trades in trades_by_market.items():
                market_info = await self._get_market_info_cached(market_id)

                if market_info and market_info.get("resolved"):
                    resolved_outcome = market_info.get("resolved_outcome")

                    # Only process if we have an actual outcome
                    if not resolved_outcome:
                        continue

                    # Get resolution time for timing analysis
                    resolution_time = datetime.utcnow()  # Approximation - when we detected resolution

                    for trade in trades:
                        is_win = self._determine_win(trade, resolved_outcome)
                        pnl = self._calculate_pnl(trade, is_win)

                        # Calculate hours before resolution for insider timing analysis
                        hours_before = (resolution_time - trade.timestamp).total_seconds() / 3600

                        trade.is_resolved = True
                        trade.resolved_outcome = resolved_outcome
                        trade.is_win = is_win
                        trade.pnl_usd = pnl
                        trade.hours_before_resolution = hours_before

                        # Clear unrealized P&L fields (no longer open position)
                        trade.unrealized_pnl_usd = None
                        trade.current_position_value_usd = None
                        trade.last_pnl_update = None

                        resolved_count += 1

                        # Update trader profile stats
                        await self._update_trader_stats(session, trade.wallet_address, is_win, pnl, trade.is_flagged)

            await session.commit()
            print(f"[ResolutionWorker] Resolved {resolved_count} trades")

    async def _update_unrealized_pnl(self):
        """
        Update unrealized P&L for all open positions (is_win IS NULL).
        Groups by market_id to minimize API calls.
        """
        async with async_session_maker() as session:
            # Get open BUY positions (unresolved trades)
            # Skip SELL positions for now as short mechanics not fully implemented
            result = await session.execute(
                select(Trade)
                .where(Trade.is_win.is_(None))
                .where(Trade.side == "BUY")
                .order_by(Trade.timestamp.desc())
                .limit(1000)  # Process in batches
            )
            open_trades = result.scalars().all()

            if not open_trades:
                print("[ResolutionWorker] No open positions to update")
                return

            print(f"[ResolutionWorker] Updating unrealized P&L for {len(open_trades)} open positions")

            # Group by market_id to minimize API calls
            trades_by_market: Dict[str, List[Trade]] = {}
            for trade in open_trades:
                if trade.market_id not in trades_by_market:
                    trades_by_market[trade.market_id] = []
                trades_by_market[trade.market_id].append(trade)

            updated_count = 0
            for market_id, trades in trades_by_market.items():
                market_info = await self._get_market_info_cached(market_id)

                if not market_info:
                    continue

                # Extract current prices from tokens
                tokens = market_info.get("tokens", [])
                current_yes_price = None
                current_no_price = None

                for token in tokens:
                    outcome = token.get("outcome", "").upper()
                    price = token.get("price")
                    if outcome == "YES" and price is not None:
                        current_yes_price = float(price)
                    elif outcome == "NO" and price is not None:
                        current_no_price = float(price)

                if current_yes_price is None or current_no_price is None:
                    continue

                # Update each trade
                for trade in trades:
                    if not trade.price or trade.price <= 0:
                        continue

                    # Calculate shares if not already stored
                    if trade.shares_held is None:
                        trade.shares_held = trade.trade_size_usd / trade.price

                    # Calculate current position value based on outcome
                    if trade.outcome and trade.outcome.upper() == "YES":
                        trade.current_position_value_usd = trade.shares_held * current_yes_price
                    elif trade.outcome and trade.outcome.upper() == "NO":
                        trade.current_position_value_usd = trade.shares_held * current_no_price
                    else:
                        continue

                    # Calculate unrealized P&L
                    trade.unrealized_pnl_usd = trade.current_position_value_usd - trade.trade_size_usd
                    trade.last_pnl_update = datetime.utcnow()
                    updated_count += 1

            await session.commit()
            print(f"[ResolutionWorker] Updated unrealized P&L for {updated_count} positions")

            # Update trader profile aggregates
            await self._update_trader_unrealized_stats(session)

    async def _update_trader_unrealized_stats(self, session: AsyncSession):
        """
        Update trader profile unrealized P&L aggregates.
        Called after updating individual trade unrealized P&L.
        """
        # Get all traders with open positions
        result = await session.execute(
            select(Trade.wallet_address)
            .where(Trade.is_win.is_(None))
            .where(Trade.unrealized_pnl_usd.isnot(None))
            .distinct()
        )
        wallet_addresses = result.scalars().all()

        for wallet_address in wallet_addresses:
            # Get all open positions for this trader
            trades_result = await session.execute(
                select(Trade)
                .where(Trade.wallet_address == wallet_address)
                .where(Trade.is_win.is_(None))
                .where(Trade.unrealized_pnl_usd.isnot(None))
            )
            open_positions = trades_result.scalars().all()

            if not open_positions:
                continue

            # Calculate aggregates
            open_count = len(open_positions)
            total_unrealized = sum(t.unrealized_pnl_usd for t in open_positions)
            avg_unrealized = total_unrealized / open_count
            total_capital = sum(t.trade_size_usd for t in open_positions)
            unrealized_roi = (total_unrealized / total_capital * 100) if total_capital > 0 else 0.0
            unrealized_wins = sum(1 for t in open_positions if t.unrealized_pnl_usd > 0)
            unrealized_win_rate = (unrealized_wins / open_count * 100) if open_count > 0 else 0.0

            # Update profile
            profile_result = await session.execute(
                select(TraderProfile).where(TraderProfile.wallet_address == wallet_address)
            )
            profile = profile_result.scalar_one_or_none()

            if profile:
                profile.open_positions_count = open_count
                profile.total_unrealized_pnl = total_unrealized
                profile.avg_unrealized_pnl = avg_unrealized
                profile.unrealized_roi = unrealized_roi
                profile.unrealized_win_count = unrealized_wins
                profile.unrealized_win_rate = unrealized_win_rate

        await session.commit()

    async def _get_market_info_cached(self, market_id: str) -> Optional[dict]:
        """
        Get market info with caching to reduce API calls.
        """
        cached = self._market_cache.get(market_id)
        if cached and cached.get("_cached_at", 0) > datetime.utcnow().timestamp() - self._cache_ttl:
            return cached

        market_info = await self.client.get_market_info(market_id)
        if market_info:
            market_info["_cached_at"] = datetime.utcnow().timestamp()
            self._market_cache[market_id] = market_info

        return market_info

    def _determine_win(self, trade: Trade, resolved_outcome: str) -> bool:
        """
        Determine if a trade won based on the resolved outcome.
        A trade wins if the trader's chosen outcome matches the resolved outcome.
        """
        if not trade.outcome or not resolved_outcome:
            return False

        return trade.outcome.upper() == resolved_outcome.upper()

    def _calculate_pnl(self, trade: Trade, is_win: bool) -> float:
        """
        Calculate profit/loss for a trade.
        - If won: profit = size * (1 - price) / price  [bought at price, resolved at $1]
        - If lost: loss = -size  [lost the entire stake]
        """
        if trade.price is None or trade.price <= 0:
            return 0.0

        if is_win:
            # Bought at price p, paid trade_size_usd total, got (trade_size_usd/p) shares
            # Each share pays $1, so payout = trade_size_usd/p
            # Profit = payout - cost = trade_size_usd/p - trade_size_usd = trade_size_usd * (1-p)/p
            return trade.trade_size_usd * (1 - trade.price) / trade.price
        else:
            # Lost entire stake
            return -trade.trade_size_usd

    async def _update_trader_stats(
        self,
        session: AsyncSession,
        wallet_address: str,
        is_win: bool,
        pnl: float,
        is_flagged: bool
    ):
        """
        Update trader profile statistics when a trade is resolved.
        """
        result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == wallet_address)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return

        profile.resolved_trades = (profile.resolved_trades or 0) + 1
        profile.total_pnl = (profile.total_pnl or 0) + pnl

        if is_win:
            profile.winning_trades = (profile.winning_trades or 0) + 1
            if is_flagged:
                profile.flagged_wins_count = (profile.flagged_wins_count or 0) + 1

        # Recalculate win rate
        if profile.resolved_trades > 0:
            profile.win_rate = (profile.winning_trades / profile.resolved_trades) * 100

        profile.last_updated = datetime.utcnow()


# Global worker instance
resolution_worker_instance = None


async def get_resolution_worker() -> TradeResolutionWorker:
    global resolution_worker_instance
    if resolution_worker_instance is None:
        resolution_worker_instance = TradeResolutionWorker()
    return resolution_worker_instance
