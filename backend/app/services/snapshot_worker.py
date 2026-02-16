import asyncio
import os
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import (
    MarketSnapshot,
    PriceHistory,
    TrackedMarket,
    async_session_maker
)
from app.services.polymarket_client import PolymarketClient


class SnapshotWorker:
    """
    Background worker that collects order book snapshots and price history
    for tracked markets at regular intervals. Used for backtesting.
    """

    def __init__(self):
        self.client = PolymarketClient()
        self.snapshot_interval = int(os.getenv("SNAPSHOT_INTERVAL_SECONDS", "300"))  # Default 5 min
        self.is_running = False
        self.max_markets_per_cycle = int(os.getenv("MAX_SNAPSHOT_MARKETS", "50"))

    async def start(self):
        """Start the background snapshot worker."""
        self.is_running = True
        print(f"[SnapshotWorker] Starting (interval: {self.snapshot_interval}s)")

        while self.is_running:
            try:
                await self._collect_snapshots()
                await asyncio.sleep(self.snapshot_interval)
            except Exception as e:
                print(f"[SnapshotWorker] Error in snapshot loop: {e}")
                await asyncio.sleep(30)  # Pause on error

    async def stop(self):
        """Stop the background worker."""
        self.is_running = False
        await self.client.close()
        print("[SnapshotWorker] Stopped")

    async def _collect_snapshots(self):
        """Collect snapshots for all tracked markets."""
        import time
        start_time = time.time()

        async with async_session_maker() as session:
            # Get active tracked markets
            result = await session.execute(
                select(TrackedMarket)
                .where(TrackedMarket.is_active == True)
                .where(TrackedMarket.is_closed == False)
                .limit(self.max_markets_per_cycle)
            )
            tracked_markets = result.scalars().all()

            if not tracked_markets:
                return

            snapshot_count = 0
            price_count = 0

            for market in tracked_markets:
                try:
                    # Collect order book snapshot
                    snapshot = await self._snapshot_market(market, session)
                    if snapshot:
                        snapshot_count += 1

                    # Collect price history
                    prices = await self._collect_price_history(market, session)
                    price_count += prices

                    # Update last snapshot time
                    market.last_snapshot_at = datetime.utcnow()

                except Exception as e:
                    print(f"[SnapshotWorker] Error snapshotting {market.market_id}: {e}")

            await session.commit()

            elapsed = time.time() - start_time
            if snapshot_count > 0:
                print(f"[SnapshotWorker] Collected {snapshot_count} snapshots, {price_count} price points [{elapsed:.1f}s]")

    async def _snapshot_market(self, market: TrackedMarket, session: AsyncSession) -> Optional[MarketSnapshot]:
        """Take an order book snapshot for a single market."""
        timestamp = datetime.utcnow()

        # Get YES token order book
        yes_book = None
        no_book = None

        if market.yes_token_id:
            yes_book = await self.client.get_order_book(market.yes_token_id)

        if market.no_token_id:
            no_book = await self.client.get_order_book(market.no_token_id)

        if not yes_book and not no_book:
            return None

        # Extract best bid/ask sizes from order book arrays (individual top-of-book size)
        yes_best_bid_size = None
        yes_best_ask_size = None
        no_best_bid_size = None
        no_best_ask_size = None

        if yes_book:
            bids = yes_book.get("bids", [])
            asks = yes_book.get("asks", [])
            if bids and len(bids) > 0:
                yes_best_bid_size = bids[0].get("size")
            if asks and len(asks) > 0:
                yes_best_ask_size = asks[0].get("size")

        if no_book:
            bids = no_book.get("bids", [])
            asks = no_book.get("asks", [])
            if bids and len(bids) > 0:
                no_best_bid_size = bids[0].get("size")
            if asks and len(asks) > 0:
                no_best_ask_size = asks[0].get("size")

        # Create snapshot
        snapshot = MarketSnapshot(
            timestamp=timestamp,
            market_id=market.market_id,
            yes_token_id=market.yes_token_id,
            no_token_id=market.no_token_id,
            # YES order book
            yes_best_bid=yes_book.get("best_bid") if yes_book else None,
            yes_best_ask=yes_book.get("best_ask") if yes_book else None,
            yes_spread=yes_book.get("spread") if yes_book else None,
            yes_bid_liquidity=yes_book.get("bid_liquidity") if yes_book else None,
            yes_ask_liquidity=yes_book.get("ask_liquidity") if yes_book else None,
            yes_best_bid_size=yes_best_bid_size,
            yes_best_ask_size=yes_best_ask_size,
            yes_mid_price=yes_book.get("mid_price") if yes_book else None,
            # NO order book
            no_best_bid=no_book.get("best_bid") if no_book else None,
            no_best_ask=no_book.get("best_ask") if no_book else None,
            no_spread=no_book.get("spread") if no_book else None,
            no_bid_liquidity=no_book.get("bid_liquidity") if no_book else None,
            no_ask_liquidity=no_book.get("ask_liquidity") if no_book else None,
            no_best_bid_size=no_best_bid_size,
            no_best_ask_size=no_best_ask_size,
            no_mid_price=no_book.get("mid_price") if no_book else None,
            # Total liquidity
            total_liquidity=(
                (yes_book.get("bid_liquidity", 0) or 0) +
                (yes_book.get("ask_liquidity", 0) or 0) +
                (no_book.get("bid_liquidity", 0) or 0) +
                (no_book.get("ask_liquidity", 0) or 0)
            ) if yes_book or no_book else None,
        )

        session.add(snapshot)
        return snapshot

    async def _collect_price_history(self, market: TrackedMarket, session: AsyncSession) -> int:
        """Fetch and store recent price history for a market."""
        count = 0
        timestamp = datetime.utcnow()

        for token_id, outcome in [(market.yes_token_id, "YES"), (market.no_token_id, "NO")]:
            if not token_id:
                continue

            # Get midpoint price (current price)
            mid_price = await self.client.get_midpoint(token_id)
            if mid_price is not None:
                price_record = PriceHistory(
                    timestamp=timestamp,
                    market_id=market.market_id,
                    token_id=token_id,
                    outcome=outcome,
                    price=mid_price,
                    interval="snapshot",
                )
                session.add(price_record)
                count += 1

        return count

    async def add_tracked_market(
        self,
        market_id: str,
        question: str = None,
        category: str = None,
        yes_token_id: str = None,
        no_token_id: str = None,
        volume: float = 0,
        liquidity: float = 0,
    ) -> TrackedMarket:
        """Add a market to the tracking list."""
        async with async_session_maker() as session:
            # Check if already tracked
            existing = await session.execute(
                select(TrackedMarket).where(TrackedMarket.market_id == market_id)
            )
            market = existing.scalar_one_or_none()

            if market:
                # Update existing
                market.is_active = True
                if yes_token_id:
                    market.yes_token_id = yes_token_id
                if no_token_id:
                    market.no_token_id = no_token_id
                if question:
                    market.question = question
                if category:
                    market.category = category
            else:
                # Create new
                market = TrackedMarket(
                    market_id=market_id,
                    question=question,
                    category=category,
                    yes_token_id=yes_token_id,
                    no_token_id=no_token_id,
                    volume=volume,
                    liquidity=liquidity,
                )
                session.add(market)

            await session.commit()
            await session.refresh(market)
            return market

    async def auto_discover_markets(
        self,
        categories: List[str] = None,
        min_liquidity: float = 10000,
        min_volume: float = 50000,
        limit: int = 50
    ) -> List[TrackedMarket]:
        """
        Auto-discover high-liquidity markets to track using Gamma API.
        Categories: 'politics', 'sports', 'crypto', etc.
        """
        import json
        print(f"[SnapshotWorker] Auto-discovering markets (categories={categories}, min_liquidity=${min_liquidity:,.0f})")

        discovered = []
        offset = 0
        page_size = 100

        while len(discovered) < limit:
            # Use Gamma API for active markets with liquidity data
            markets = await self.client.get_markets_list(limit=page_size, offset=offset, closed=False)

            if not markets:
                break

            # Sort by liquidity (highest first)
            markets.sort(key=lambda m: float(m.get("liquidityNum", 0) or 0), reverse=True)

            for m in markets:
                # Check liquidity and volume thresholds
                liquidity = float(m.get("liquidityNum", 0) or 0)
                volume = float(m.get("volumeNum", 0) or 0)

                if liquidity < min_liquidity or volume < min_volume:
                    continue

                # Parse token IDs from clobTokenIds JSON string
                yes_token_id = None
                no_token_id = None
                clob_tokens_str = m.get("clobTokenIds", "[]")
                try:
                    clob_tokens = json.loads(clob_tokens_str)
                    # Usually [yes_token, no_token] order based on outcomes
                    outcomes_str = m.get("outcomes", '["Yes", "No"]')
                    outcomes = json.loads(outcomes_str)
                    if len(clob_tokens) >= 2 and len(outcomes) >= 2:
                        for i, outcome in enumerate(outcomes):
                            if outcome.lower() == "yes" and i < len(clob_tokens):
                                yes_token_id = clob_tokens[i]
                            elif outcome.lower() == "no" and i < len(clob_tokens):
                                no_token_id = clob_tokens[i]
                except (json.JSONDecodeError, TypeError):
                    continue

                if not yes_token_id or not no_token_id:
                    continue

                # Check category if filtering
                question = m.get("question", "").lower()
                detected_category = None
                if categories:
                    category_match = False
                    for cat in categories:
                        cat_lower = cat.lower()
                        if cat_lower in question:
                            category_match = True
                            detected_category = cat
                            break
                        # Check common keywords
                        if cat_lower == "politics" and any(kw in question for kw in ["election", "president", "congress", "senate", "trump", "biden", "democrat", "republican"]):
                            category_match = True
                            detected_category = "politics"
                            break
                        if cat_lower == "sports" and any(kw in question for kw in ["nba", "nfl", "mlb", "nhl", "super bowl", "playoffs", "championship", "game", "win", "score"]):
                            category_match = True
                            detected_category = "sports"
                            break
                        if cat_lower == "crypto" and any(kw in question for kw in ["bitcoin", "btc", "ethereum", "eth", "crypto", "price"]):
                            category_match = True
                            detected_category = "crypto"
                            break

                    if not category_match:
                        continue

                # Add to tracking
                tracked = await self.add_tracked_market(
                    market_id=m.get("conditionId"),
                    question=m.get("question"),
                    category=detected_category,
                    yes_token_id=yes_token_id,
                    no_token_id=no_token_id,
                    volume=volume,
                    liquidity=liquidity,
                )
                discovered.append(tracked)
                print(f"[SnapshotWorker] Added: {m.get('question', '')[:60]}... (${liquidity:,.0f} liq)")

                if len(discovered) >= limit:
                    break

            offset += page_size
            # Stop if we've gone through several pages without finding enough
            if offset > 500:
                break

        print(f"[SnapshotWorker] Discovered {len(discovered)} markets to track")
        return discovered

    async def backfill_price_history(
        self,
        market_id: str,
        token_id: str,
        outcome: str,
        interval: str = "1h",
        fidelity: int = 60,
        days_back: int = 30
    ) -> int:
        """
        Backfill historical price data for a market.
        Fetches from CLOB API and stores in PriceHistory table.
        """
        print(f"[SnapshotWorker] Backfilling {days_back} days of {interval} data for {market_id} ({outcome})")

        end_ts = int(datetime.utcnow().timestamp())
        start_ts = int((datetime.utcnow() - timedelta(days=days_back)).timestamp())

        history = await self.client.get_price_history(
            token_id=token_id,
            start_ts=start_ts,
            end_ts=end_ts,
            fidelity=fidelity
        )

        if not history:
            print(f"[SnapshotWorker] No history returned for {token_id}")
            return 0

        count = 0
        async with async_session_maker() as session:
            for point in history:
                ts = datetime.fromtimestamp(point["timestamp"])
                price = point["price"]

                # Check for duplicate
                existing = await session.execute(
                    select(PriceHistory).where(
                        and_(
                            PriceHistory.market_id == market_id,
                            PriceHistory.token_id == token_id,
                            PriceHistory.timestamp == ts
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    continue

                record = PriceHistory(
                    timestamp=ts,
                    market_id=market_id,
                    token_id=token_id,
                    outcome=outcome,
                    price=price,
                    interval=interval,
                )
                session.add(record)
                count += 1

            await session.commit()

        print(f"[SnapshotWorker] Backfilled {count} price points for {market_id} ({outcome})")
        return count


# Global worker instance
snapshot_worker_instance = None


async def get_snapshot_worker() -> SnapshotWorker:
    global snapshot_worker_instance
    if snapshot_worker_instance is None:
        snapshot_worker_instance = SnapshotWorker()
    return snapshot_worker_instance
