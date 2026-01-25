import asyncio
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import Trade, async_session_maker
from app.services.polymarket_client import PolymarketClient
from app.services.insider_detector import InsiderDetector
import os


class DataIngestionWorker:
    def __init__(self):
        self.client = PolymarketClient()
        self.detector = InsiderDetector()
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
        self.min_trade_size = float(os.getenv("MIN_TRADE_SIZE_USD", "50"))
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
            trades = await self.client.get_recent_trades(limit=1000)
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

            # Filter out bot trades / small trades
            if trade_size_usd < self.min_trade_size:
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
            market_name = trade_data.get("market_name", "Unknown Market")
            timestamp = datetime.fromtimestamp(int(trade_data.get("timestamp", 0)) / 1000)

            # NEW: Parse trade direction and type
            side = trade_data.get("side", "").upper()  # BUY or SELL
            if side not in ("BUY", "SELL"):
                side = None

            # Determine outcome (YES/NO) from the trade
            outcome = trade_data.get("outcome", "")
            if outcome not in ("YES", "NO"):
                outcome = None

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
                await self.detector.update_trader_profile(wallet_address, session)

            return trade

        except Exception as e:
            print(f"[Worker] Error processing trade: {e}")
            return None


# Global worker instance
worker_instance = None


async def get_worker() -> DataIngestionWorker:
    global worker_instance
    if worker_instance is None:
        worker_instance = DataIngestionWorker()
    return worker_instance
