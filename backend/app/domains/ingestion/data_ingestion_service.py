import logging
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
import uuid
import os
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import Trade, async_session_maker
from app.domains.traders.repository import TraderRepository
from app.domains.ingestion.polymarket_client import PolymarketClient
from app.domains.ingestion.insider_detector import InsiderDetector

logger = logging.getLogger(__name__)

class DataIngestionService:
    def __init__(self):
        from app.core.config import get_settings
        self.settings = get_settings()
        self.trader_repo = TraderRepository()
        self.client = PolymarketClient()
        self.detector = InsiderDetector()
        self.min_trade_size = self.settings.min_trade_size_filter
        self.trade_fetch_limit = self.settings.trade_fetch_limit
        self.tracked_markets = set(self.settings.tracked_market_id_list)

        if self.tracked_markets:
            logger.info(f"[Worker] Tracking {len(self.tracked_markets)} specific markets: {list(self.tracked_markets)}")
        else:
            logger.info(f"[Worker] Tracking ALL markets (no filter configured)")

    async def process_trades(self) -> dict:
        import time
        start_time = time.time()
        new_trades = 0
        flagged_trades = 0

        async with async_session_maker() as session:
            trades = await self.client.get_recent_trades(limit=self.trade_fetch_limit)
            fetch_time = time.time() - start_time

            for trade_data in trades:
                result = await self.process_single_trade(trade_data, session)
                if result:
                    new_trades += 1
                    if result.is_flagged:
                        flagged_trades += 1

            await session.commit()
            total_time = time.time() - start_time
            if new_trades > 0:
                logger.info(f"[Ingestion] Ingested {new_trades} new trades ({flagged_trades} flagged) [fetch: {fetch_time:.1f}s, total: {total_time:.1f}s]")
                
        return {"new_trades": new_trades, "flagged_trades": flagged_trades}

    async def process_single_trade(self, trade_data: dict, session: AsyncSession) -> Optional[Trade]:
        try:
            # Filter by tracked markets if configured
            market_id = trade_data.get("market", "")
            if self.tracked_markets and market_id not in self.tracked_markets:
                return None  # Skip trades from non-tracked markets

            wallet_address = trade_data.get("maker_address", "")
            trade_size_usd = float(trade_data.get("size", 0))

            if self.min_trade_size > 0 and trade_size_usd < self.min_trade_size:
                return None

            transaction_hash = trade_data.get("id", "") or f"unknown_{uuid.uuid4().hex[:16]}"

            if transaction_hash:
                existing = await self.trader_repo.get_trade_by_transaction_hash(session, transaction_hash)
                if existing:
                    return None

            market_slug = trade_data.get("event_slug", "")
            market_name = trade_data.get("market_name", "Unknown Market")
            timestamp = datetime.fromtimestamp(int(trade_data.get("timestamp", 0)) / 1000)
            side = trade_data.get("side", "").upper()
            if side not in ("BUY", "SELL"):
                side = None

            outcome = trade_data.get("outcome", "")
            price = float(trade_data.get("price", 0))
            asset_id = trade_data.get("asset_id", "")

            z_score, is_flagged = await self.detector.calculate_z_score(
                wallet_address, trade_size_usd, session
            )

            flag_reason = None
            if is_flagged:
                if z_score > 0:
                    flag_reason = f"Unusually large bet (z-score: {z_score:.2f})"
                else:
                    flag_reason = f"Unusually small bet (z-score: {z_score:.2f})"

            trade = Trade(
                wallet_address=wallet_address,
                market_id=market_id,
                market_slug=market_slug,
                market_name=market_name,
                trade_size_usd=trade_size_usd,
                outcome=outcome,
                price=price,
                timestamp=timestamp,
                is_flagged=is_flagged,
                flag_reason=flag_reason,
                z_score=z_score,
                side=side,
                trade_type=None,
                transaction_hash=transaction_hash,
                asset_id=asset_id if asset_id else None,
                trade_hour_utc=timestamp.hour,
            )

            session.add(trade)

            if is_flagged:
                profile = await self.detector.update_trader_profile(wallet_address, session)
                if profile and profile.total_trades < 50:
                    asyncio.create_task(self.backfill_trader_history(wallet_address))

            return trade

        except Exception as e:
            logger.error(f"[Ingestion] Error processing trade: {e}")
            return None

    async def backfill_trader_history(self, wallet_address: str):
        logger.info(f"[Ingestion] Backfilling history for {wallet_address}...")
        try:
            activity = await self.client.get_user_activity(wallet_address, limit=500)
            if not activity:
                return

            async with async_session_maker() as session:
                count = 0
                for item in activity:
                    txn_hash = item.get("transactionHash")
                    if not txn_hash:
                        continue
                        
                    existing = await self.trader_repo.get_trade_by_transaction_hash(session, txn_hash)
                    if existing:
                        continue
                        
                    market_id = item.get("conditionId") or ""
                    if item.get("type", "").upper() not in ("TRADE", "ERC1155_TRANSFER", "CTF_TRADE"):
                        continue
                        
                    price = float(item.get("price", 0))
                    size = float(item.get("usdcSize", 0))
                    
                    if self.min_trade_size > 0 and size < self.min_trade_size:
                        continue
                        
                    timestamp = datetime.fromtimestamp(int(item.get("timestamp", 0)))
                    
                    trade = Trade(
                        wallet_address=wallet_address,
                        market_id=market_id,
                        market_name=item.get("title") or "Backfilled Trade",
                        market_slug=item.get("eventSlug"),
                        trade_size_usd=size,
                        outcome=item.get("outcome"),
                        price=price,
                        timestamp=timestamp,
                        is_flagged=False,
                        side=item.get("side", "").upper(),
                        transaction_hash=txn_hash,
                        trade_hour_utc=timestamp.hour
                    )
                    
                    session.add(trade)
                    count += 1
                
                await session.commit()
                if count > 0:
                    logger.info(f"[Ingestion] Backfilled {count} trades for {wallet_address}")
                    await self.detector.update_trader_profile(wallet_address, session)
                    
        except Exception as e:
            logger.error(f"[Ingestion] Error backfilling {wallet_address}: {e}")

    async def backfill_historical_trades(
        self,
        max_pages: int = 10000,
        target_market_ids: set = None,
        days_back: int = None,
        stop_on_duplicates: bool = False,
        batch_size: int = 500
    ):
        """
        Optimized backfill with bulk inserts and minimal overhead.

        Args:
            max_pages: Maximum pages to fetch (500 trades/page)
            target_market_ids: Set of market IDs to filter for (None = all)
            days_back: Stop backfilling after going back this many days
            stop_on_duplicates: Stop if 3 consecutive empty pages
            batch_size: Number of trades to accumulate before bulk insert

        Returns:
            Total number of new trades inserted
        """
        logger.info(f"[Backfill] Starting optimized backfill (max {max_pages} pages)...")

        from app.core.config import get_settings
        settings = get_settings()
        rate_limit_delay = settings.backfill_rate_limit_delay

        total_new = 0
        pages_fetched = 0
        oldest_timestamp = None
        trade_batch = []

        # Calculate cutoff date if days_back specified
        cutoff_date = None
        if days_back:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            logger.info(f"[Backfill] Will stop at {cutoff_date.strftime('%Y-%m-%d')}")

        async with async_session_maker() as session:
            for page in range(max_pages):
                # Fetch page of trades
                trades = await self.client.get_historical_trades(
                    before_timestamp=oldest_timestamp,
                    limit=500
                )

                if not trades:
                    logger.info(f"[Backfill] No more trades found after {pages_fetched} pages")
                    break

                pages_fetched += 1

                # Process trades in this page
                for trade_data in trades:
                    # Filter by market
                    if target_market_ids:
                        market_id = trade_data.get("market", "")
                        if market_id not in target_market_ids:
                            continue

                    # Create trade object (without deduplication check for speed)
                    trade = self._create_trade_object_for_bulk(trade_data)
                    if trade:
                        trade_batch.append(trade)

                # Bulk insert when batch is full
                if len(trade_batch) >= batch_size:
                    inserted = await self._bulk_insert_trades(session, trade_batch)
                    total_new += inserted
                    trade_batch = []

                # Update pagination cursor
                oldest_timestamp = min(t.get("timestamp", 0) for t in trades)
                oldest_date = datetime.fromtimestamp(oldest_timestamp / 1000)

                # Log every 10 pages to reduce noise
                if pages_fetched % 10 == 0:
                    logger.info(
                        f"[Backfill] Page {pages_fetched}: {total_new} trades inserted "
                        f"(oldest: {oldest_date.strftime('%Y-%m-%d %H:%M')})"
                    )

                # Check cutoff date
                if cutoff_date and oldest_date < cutoff_date:
                    logger.info(f"[Backfill] Reached target date, stopping")
                    break

                # Rate limiting
                await asyncio.sleep(rate_limit_delay)

            # Insert remaining batch
            if trade_batch:
                inserted = await self._bulk_insert_trades(session, trade_batch)
                total_new += inserted

            await session.commit()

        logger.info(f"[Backfill] Complete: {total_new} trades inserted, {pages_fetched} pages fetched")
        return total_new

    def _create_trade_object_for_bulk(self, trade_data: dict) -> Optional[Trade]:
        """
        Create Trade object without database queries (for bulk insert).
        Skips Z-score calculation and deduplication checks for speed.
        """
        try:
            transaction_hash = trade_data.get("id", "") or f"unknown_{uuid.uuid4().hex[:16]}"
            market_id = trade_data.get("market", "")
            wallet_address = trade_data.get("maker_address", "")

            if not market_id or not wallet_address:
                return None

            trade_size = float(trade_data.get("size", 0))
            if trade_size < self.min_trade_size:
                return None

            # Convert timestamp
            timestamp_ms = trade_data.get("timestamp", 0)
            if isinstance(timestamp_ms, int):
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
            else:
                logger.warning(f"Invalid timestamp format for trade: {trade_data.get('id')}. Skipping.")
                return None

            trade = Trade(
                transaction_hash=transaction_hash,
                wallet_address=wallet_address,
                market_id=market_id,
                market_slug=trade_data.get("event_slug", ""),
                market_name=trade_data.get("market_name", "Unknown"),
                trade_size_usd=trade_size,
                outcome=trade_data.get("outcome", ""),
                price=float(trade_data.get("price", 0)) if trade_data.get("price") else None,
                side=trade_data.get("side", ""),
                asset_id=trade_data.get("asset_id", ""),
                timestamp=timestamp,
                trade_hour_utc=timestamp.hour,
                is_flagged=False,
                z_score=None
            )

            return trade
        except Exception as e:
            logger.error(f"Error creating trade object: {e}")
            return None

    async def _bulk_insert_trades(self, session: AsyncSession, trades: List[Trade]) -> int:
        """
        Bulk insert trades using PostgreSQL ON CONFLICT DO NOTHING.
        Returns estimated count of successfully inserted trades.

        Note: PostgreSQL doesn't return exact count with ON CONFLICT,
        so we return batch size as estimate.
        """
        if not trades:
            return 0

        try:
            from sqlalchemy.dialects.postgresql import insert

            # Build list of dictionaries for bulk insert
            trade_dicts = []
            for t in trades:
                trade_dicts.append({
                    "transaction_hash": t.transaction_hash,
                    "wallet_address": t.wallet_address,
                    "market_id": t.market_id,
                    "market_slug": t.market_slug,
                    "market_name": t.market_name,
                    "trade_size_usd": t.trade_size_usd,
                    "outcome": t.outcome,
                    "price": t.price,
                    "side": t.side,
                    "asset_id": t.asset_id,
                    "timestamp": t.timestamp,
                    "trade_hour_utc": t.trade_hour_utc,
                    "is_flagged": t.is_flagged,
                    "z_score": t.z_score
                })

            # Bulk insert with ON CONFLICT DO NOTHING
            stmt = insert(Trade).values(trade_dicts)
            stmt = stmt.on_conflict_do_nothing(
                index_elements=['transaction_hash']  # Unique index
            )

            await session.execute(stmt)

            # Return batch size as estimate (can't get exact count with ON CONFLICT)
            return len(trades)
        except Exception as e:
            logger.error(f"Error in bulk insert: {e}")

            # Fallback to individual inserts
            count = 0
            for trade in trades:
                try:
                    session.add(trade)
                    count += 1
                except IntegrityError:
                    pass  # Skip duplicates

            return count

    async def backfill_multiple_markets_parallel(
        self,
        market_ids: List[str],
        max_pages_per_market: int = 10000
    ):
        """
        Backfill multiple markets in parallel using asyncio.gather.
        Each market gets its own backfill task running concurrently.

        Args:
            market_ids: List of market condition IDs to backfill
            max_pages_per_market: Max pages to fetch for each market

        Returns:
            Total number of trades inserted across all markets
        """
        logger.info(f"[Backfill] Starting parallel backfill for {len(market_ids)} markets...")

        # Create backfill task for each market
        tasks = []
        for market_id in market_ids:
            task = self.backfill_historical_trades(
                max_pages=max_pages_per_market,
                target_market_ids={market_id},
                stop_on_duplicates=False
            )
            tasks.append(task)

        # Run all backfills concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Sum successful results
        total_trades = 0
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"[Backfill] Market {market_ids[i]} failed: {result}")
            else:
                logger.info(f"[Backfill] Market {market_ids[i]}: {result} trades")
                total_trades += result

        logger.info(f"[Backfill] Parallel backfill complete: {total_trades} total trades")
        return total_trades
