import json
import logging
from datetime import datetime, timedelta

from app.core.database import MarketSnapshot, PriceHistory, TrackedMarket, async_session_maker
from app.domains.ingestion.polymarket_client import PolymarketClient
from app.domains.markets.repository import MarketRepository

logger = logging.getLogger(__name__)


class SnapshotService:
    def __init__(self):
        self.market_repo = MarketRepository()
        self.client = PolymarketClient()

    async def collect_snapshots(self, max_markets: int):
        import time

        start_time = time.time()

        async with async_session_maker() as session:
            tracked_markets = await self.market_repo.get_active_tracked_markets(session, max_markets)

            if not tracked_markets:
                return

            snapshot_count = 0
            price_count = 0

            for market in tracked_markets:
                try:
                    snapshot = await self.snapshot_market(market, session)
                    if snapshot:
                        snapshot_count += 1

                    prices = await self.collect_price_history(market, session)
                    price_count += prices

                    market.last_snapshot_at = datetime.utcnow()

                except Exception as e:
                    logger.error(f"[SnapshotService] Error snapshotting {market.market_id}: {e}")

            await session.commit()
            elapsed = time.time() - start_time
            if snapshot_count > 0:
                logger.info(
                    f"[SnapshotService] Collected {snapshot_count} snapshots, {price_count} price points [{elapsed:.1f}s]"
                )

    async def snapshot_market(self, market: TrackedMarket, session) -> MarketSnapshot | None:
        timestamp = datetime.utcnow()
        yes_book = None
        no_book = None

        if market.yes_token_id:
            yes_book = await self.client.get_order_book(market.yes_token_id)
        if market.no_token_id:
            no_book = await self.client.get_order_book(market.no_token_id)

        if not yes_book and not no_book:
            return None

        yes_best_bid_size = None
        yes_best_ask_size = None
        no_best_bid_size = None
        no_best_ask_size = None

        if yes_book:
            bids = yes_book.get("bids", [])
            asks = yes_book.get("asks", [])
            if bids:
                yes_best_bid_size = bids[0].get("size")
            if asks:
                yes_best_ask_size = asks[0].get("size")

        if no_book:
            bids = no_book.get("bids", [])
            asks = no_book.get("asks", [])
            if bids:
                no_best_bid_size = bids[0].get("size")
            if asks:
                no_best_ask_size = asks[0].get("size")

        snapshot = MarketSnapshot(
            timestamp=timestamp,
            market_id=market.market_id,
            yes_token_id=market.yes_token_id,
            no_token_id=market.no_token_id,
            yes_best_bid=yes_book.get("best_bid") if yes_book else None,
            yes_best_ask=yes_book.get("best_ask") if yes_book else None,
            yes_spread=yes_book.get("spread") if yes_book else None,
            yes_bid_liquidity=yes_book.get("bid_liquidity") if yes_book else None,
            yes_ask_liquidity=yes_book.get("ask_liquidity") if yes_book else None,
            yes_best_bid_size=yes_best_bid_size,
            yes_best_ask_size=yes_best_ask_size,
            yes_mid_price=yes_book.get("mid_price") if yes_book else None,
            no_best_bid=no_book.get("best_bid") if no_book else None,
            no_best_ask=no_book.get("best_ask") if no_book else None,
            no_spread=no_book.get("spread") if no_book else None,
            no_bid_liquidity=no_book.get("bid_liquidity") if no_book else None,
            no_ask_liquidity=no_book.get("ask_liquidity") if no_book else None,
            no_best_bid_size=no_best_bid_size,
            no_best_ask_size=no_best_ask_size,
            no_mid_price=no_book.get("mid_price") if no_book else None,
            total_liquidity=(
                (yes_book.get("bid_liquidity", 0) or 0)
                + (yes_book.get("ask_liquidity", 0) or 0)
                + (no_book.get("bid_liquidity", 0) or 0)
                + (no_book.get("ask_liquidity", 0) or 0)
            )
            if yes_book or no_book
            else None,
        )

        session.add(snapshot)
        return snapshot

    async def collect_price_history(self, market: TrackedMarket, session) -> int:
        count = 0
        timestamp = datetime.utcnow()

        for token_id, outcome in [(market.yes_token_id, "YES"), (market.no_token_id, "NO")]:
            if not token_id:
                continue

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
        async with async_session_maker() as session:
            market = await self.market_repo.get_tracked_market_by_id(session, market_id)

            if market:
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
        self, categories: list[str] = None, min_liquidity: float = 10000, min_volume: float = 50000, limit: int = 50
    ) -> list[TrackedMarket]:
        logger.info(
            f"[SnapshotService] Auto-discovering markets (categories={categories}, min_liquidity=${min_liquidity:,.0f})"
        )
        discovered = []
        offset = 0
        page_size = 100

        while len(discovered) < limit:
            markets = await self.client.get_markets_list(limit=page_size, offset=offset, closed=False)

            if not markets:
                break

            markets.sort(key=lambda m: float(m.get("liquidityNum", 0) or 0), reverse=True)

            for m in markets:
                liquidity = float(m.get("liquidityNum", 0) or 0)
                volume = float(m.get("volumeNum", 0) or 0)

                if liquidity < min_liquidity or volume < min_volume:
                    continue

                yes_token_id = None
                no_token_id = None
                clob_tokens_str = m.get("clobTokenIds", "[]")
                try:
                    clob_tokens = json.loads(clob_tokens_str)
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
                        if cat_lower == "politics" and any(
                            kw in question
                            for kw in [
                                "election",
                                "president",
                                "congress",
                                "senate",
                                "trump",
                                "biden",
                                "democrat",
                                "republican",
                            ]
                        ):
                            category_match = True
                            detected_category = "politics"
                            break
                        if cat_lower == "sports" and any(
                            kw in question
                            for kw in [
                                "nba",
                                "nfl",
                                "mlb",
                                "nhl",
                                "super bowl",
                                "playoffs",
                                "championship",
                                "game",
                                "win",
                                "score",
                            ]
                        ):
                            category_match = True
                            detected_category = "sports"
                            break
                        if cat_lower == "crypto" and any(
                            kw in question for kw in ["bitcoin", "btc", "ethereum", "eth", "crypto", "price"]
                        ):
                            category_match = True
                            detected_category = "crypto"
                            break

                    if not category_match:
                        continue

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
                logger.info(f"[SnapshotService] Added: {m.get('question', '')[:60]}... (${liquidity:,.0f} liq)")

                if len(discovered) >= limit:
                    break

            offset += page_size
            if offset > 500:
                break

        logger.info(f"[SnapshotService] Discovered {len(discovered)} markets to track")
        return discovered

    async def backfill_price_history(
        self, market_id: str, token_id: str, outcome: str, interval: str = "1h", fidelity: int = 60, days_back: int = 30
    ) -> int:
        logger.info(f"[SnapshotService] Backfilling {days_back} days of {interval} data for {market_id} ({outcome})")

        end_ts = int(datetime.utcnow().timestamp())
        start_ts = int((datetime.utcnow() - timedelta(days=days_back)).timestamp())

        history = await self.client.get_price_history(
            token_id=token_id, start_ts=start_ts, end_ts=end_ts, fidelity=fidelity
        )

        if not history:
            return 0

        count = 0
        async with async_session_maker() as session:
            for point in history:
                ts = datetime.fromtimestamp(point["timestamp"])
                price = point["price"]

                existing = await self.market_repo.get_price_history_record(session, market_id, token_id, ts)
                if existing:
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

        logger.info(f"[SnapshotService] Backfilled {count} price points for {market_id} ({outcome})")
        return count
