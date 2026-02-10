import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import Trade, async_session_maker
from app.services.polymarket_client import PolymarketClient
from app.services.insider_detector import InsiderDetector
from typing import List, Dict, Any
import os
import asyncio


class DataIngestionWorker:
    def __init__(self):
        self.client = PolymarketClient()
        self.detector = InsiderDetector()
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
        self.min_trade_size = float(os.getenv("MIN_TRADE_SIZE_USD", "0"))  # Default 0 = no filter
        self.trade_fetch_limit = int(os.getenv("TRADE_FETCH_LIMIT", "1000"))
        self.is_running = False

    async def start(self):
        """
        Start the background worker that continuously polls Polymarket API.
        """
        self.is_running = True
        print(f"[Worker] Starting data ingestion worker (poll interval: {self.poll_interval}s)")

        while self.is_running:
            try:
                await self._process_trades()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                print(f"[Worker] Error in ingestion loop: {e}")
                await asyncio.sleep(5)  # Brief pause on error

    async def stop(self):
        """
        Stop the background worker.
        """
        self.is_running = False
        await self.client.close()
        print("[Worker] Data ingestion worker stopped")

    async def _process_trades(self):
        """
        Fetch trades from API, calculate z-scores, and store in database.
        """
        import time
        start_time = time.time()

        async with async_session_maker() as session:
            trades = await self.client.get_recent_trades(limit=self.trade_fetch_limit)
            fetch_time = time.time() - start_time

            new_trades = 0
            flagged_trades = 0

            for trade_data in trades:
                result = await self._process_single_trade(trade_data, session)
                if result:
                    new_trades += 1
                    if result.is_flagged:
                        flagged_trades += 1

            await session.commit()
            total_time = time.time() - start_time
            if new_trades > 0:
                print(f"[Worker] Ingested {new_trades} new trades ({flagged_trades} flagged) [fetch: {fetch_time:.1f}s, total: {total_time:.1f}s]")

    async def _process_single_trade(self, trade_data: dict, session: AsyncSession) -> Optional[Trade]:
        """
        Process a single trade: calculate z-score and store.
        Returns the Trade object if created, None if skipped.
        """
        try:
            wallet_address = trade_data.get("maker_address", "")
            trade_size_usd = float(trade_data.get("size", 0))

            # Filter out bot trades / small trades (disabled by default, set MIN_TRADE_SIZE_USD to enable)
            if self.min_trade_size > 0 and trade_size_usd < self.min_trade_size:
                return None

            # Get transaction hash for deduplication (primary method)
            transaction_hash = trade_data.get("id", "")

            # Skip if trade already exists using transaction_hash (best deduplication)
            if transaction_hash:
                existing = await session.execute(
                    select(Trade).where(Trade.transaction_hash == transaction_hash)
                )
                if existing.scalar_one_or_none():
                    return None

            # Parse all trade fields
            market_id = trade_data.get("market", "")
            market_slug = trade_data.get("event_slug", "")
            market_name = trade_data.get("market_name", "Unknown Market")
            timestamp = datetime.fromtimestamp(int(trade_data.get("timestamp", 0)) / 1000)

            # NEW: Parse trade direction and type
            side = trade_data.get("side", "").upper()  # BUY or SELL
            if side not in ("BUY", "SELL"):
                side = None

            # Determine outcome (YES/NO/Up/Down/TeamName) from the trade
            outcome = trade_data.get("outcome", "")
            # Removed strict YES/NO check to support all market types


            # Parse price (0-1 decimal representing probability)
            price = float(trade_data.get("price", 0))

            # Asset ID for tracking specific tokens
            asset_id = trade_data.get("asset_id", "")

            # Calculate z-score for anomaly detection
            z_score, is_flagged = await self.detector.calculate_z_score(
                wallet_address, trade_size_usd, session
            )

            # Determine flag reason if flagged
            flag_reason = None
            if is_flagged:
                if z_score > 0:
                    flag_reason = f"Unusually large bet (z-score: {z_score:.2f})"
                else:
                    flag_reason = f"Unusually small bet (z-score: {z_score:.2f})"

            # Create trade record with all new fields
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
                # Trade direction fields
                side=side,
                trade_type=None,  # Not available from API yet
                transaction_hash=transaction_hash if transaction_hash else None,
                asset_id=asset_id if asset_id else None,
                # Timing analysis field
                trade_hour_utc=timestamp.hour,
            )

            session.add(trade)

            # Update trader profile if this is a flagged trade
            if is_flagged:
                profile = await self.detector.update_trader_profile(wallet_address, session)
                
                # Check for backfill if profile exists and has few trades (indicating new discovery)
                if profile and profile.total_trades < 50:
                    # Trigger background backfill
                    asyncio.create_task(self._backfill_trader_history(wallet_address))

            return trade

        except Exception as e:
            print(f"[Worker] Error processing trade: {e}")
            return None

    async def _backfill_trader_history(self, wallet_address: str):
        """
        Fetch historical trades for a wallet to populate profile stats immediately.
        """
        print(f"[Worker] Backfilling history for {wallet_address}...")
        try:
            # Polymarket API returns recent activity
            activity = await self.client.get_user_activity(wallet_address, limit=500)
            
            if not activity:
                return

            async with async_session_maker() as session:
                count = 0
                for item in activity:
                    # Parse activity item to Trade format
                    txn_hash = item.get("transactionHash")
                    if not txn_hash:
                        continue
                        
                    # Skip if exists
                    existing = await session.execute(
                        select(Trade).where(Trade.transaction_hash == txn_hash)
                    )
                    if existing.scalar_one_or_none():
                        continue
                        
                    # Extract fields
                    market_id = item.get("conditionId") or "" # Activity might not have conditionId sometimes?
                    # Check if type is trade
                    if item.get("type", "").upper() not in ("TRADE", "ERC1155_TRANSFER", "CTF_TRADE"):
                        continue
                        
                    # Attempt to reconstruct trade
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
                    
                    # We might not have resolution info yet, resolution worker will pick it up
                    session.add(trade)
                    count += 1
                
                await session.commit()
                if count > 0:
                    print(f"[Worker] Backfilled {count} trades for {wallet_address}")
                    # Update profile again with full history
                    await self.detector.update_trader_profile(wallet_address, session)
                    
        except Exception as e:
            print(f"[Worker] Error backfilling {wallet_address}: {e}")


    async def backfill_historical_trades(
        self,
        max_pages: int = 100,
        target_market_ids: set = None,
        days_back: int = None,
        stop_on_duplicates: bool = True
    ):
        """
        Backfill historical trades by paginating through the API.

        Args:
            max_pages: Maximum number of pages to fetch (each page ~500 trades)
            target_market_ids: Optional set of market IDs to filter for. If None, fetches all.
            days_back: Optional - keep going until we reach this many days in the past
            stop_on_duplicates: If False, keep going even when finding duplicates (for deep backfill)
        """
        print(f"[Backfill] Starting historical trade backfill (max {max_pages} pages, days_back={days_back})...")

        if days_back:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            print(f"[Backfill] Will fetch back to {cutoff_date.strftime('%Y-%m-%d')}")

        total_new = 0
        total_skipped = 0
        pages_fetched = 0
        oldest_timestamp = None
        consecutive_empty_pages = 0

        async with async_session_maker() as session:
            for page in range(max_pages):
                # Fetch trades, using oldest timestamp for pagination
                trades = await self.client.get_historical_trades(
                    before_timestamp=oldest_timestamp,
                    limit=500
                )

                if not trades:
                    print(f"[Backfill] No more trades found after {pages_fetched} pages")
                    break

                pages_fetched += 1
                page_new = 0

                for trade_data in trades:
                    # Filter by market if target_market_ids specified
                    if target_market_ids:
                        market_id = trade_data.get("market", "")
                        if market_id not in target_market_ids:
                            continue

                    # Process the trade (will skip if already exists)
                    result = await self._process_single_trade(trade_data, session)
                    if result:
                        page_new += 1
                        total_new += 1
                    else:
                        total_skipped += 1

                # Get oldest timestamp for next page
                if trades:
                    oldest_timestamp = min(t.get("timestamp", 0) for t in trades)
                    oldest_date = datetime.fromtimestamp(oldest_timestamp / 1000)
                    print(f"[Backfill] Page {pages_fetched}: {page_new} new trades (oldest: {oldest_date.strftime('%Y-%m-%d %H:%M')})")

                    # Check if we've gone back far enough
                    if days_back and oldest_date < cutoff_date:
                        print(f"[Backfill] Reached target date {cutoff_date.strftime('%Y-%m-%d')}, stopping")
                        break

                # Commit every page to avoid memory issues
                await session.commit()

                # Small delay to avoid rate limiting
                await asyncio.sleep(0.3)

                # Track consecutive empty pages
                if page_new == 0:
                    consecutive_empty_pages += 1
                else:
                    consecutive_empty_pages = 0

                # Stop logic based on settings
                if stop_on_duplicates and consecutive_empty_pages >= 3:
                    print(f"[Backfill] {consecutive_empty_pages} consecutive pages with no new trades, stopping")
                    break

        print(f"[Backfill] Complete: {total_new} new trades, {total_skipped} skipped, {pages_fetched} pages")
        return total_new


# Global worker instance
worker_instance = None


async def get_worker() -> DataIngestionWorker:
    global worker_instance
    if worker_instance is None:
        worker_instance = DataIngestionWorker()
    return worker_instance


async def run_backfill(max_pages: int = 100, days_back: int = None, stop_on_duplicates: bool = True):
    """Standalone function to run historical backfill"""
    worker = await get_worker()
    return await worker.backfill_historical_trades(
        max_pages=max_pages,
        days_back=days_back,
        stop_on_duplicates=stop_on_duplicates
    )
