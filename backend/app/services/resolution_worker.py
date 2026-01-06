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
        """
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

                    for trade in trades:
                        is_win = self._determine_win(trade, resolved_outcome)
                        pnl = self._calculate_pnl(trade, is_win)

                        trade.is_resolved = True
                        trade.resolved_outcome = resolved_outcome
                        trade.is_win = is_win
                        trade.pnl_usd = pnl

                        resolved_count += 1

                        # Update trader profile stats
                        await self._update_trader_stats(session, trade.wallet_address, is_win, pnl, trade.is_flagged)

            await session.commit()
            print(f"[ResolutionWorker] Resolved {resolved_count} trades")

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
        - If won: profit = size * (1 - price)  [bought at price, resolved at $1]
        - If lost: loss = -size * price  [lost the amount paid]
        """
        if trade.price is None:
            return 0.0

        if is_win:
            return trade.trade_size_usd * (1 - trade.price)
        else:
            return -trade.trade_size_usd * trade.price

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
