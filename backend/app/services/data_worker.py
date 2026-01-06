import asyncio
from datetime import datetime
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
        async with async_session_maker() as session:
            trades = await self.client.get_recent_trades(limit=1000)

            for trade_data in trades:
                await self._process_single_trade(trade_data, session)

            await session.commit()
            print(f"[Worker] Processed {len(trades)} trades")

    async def _process_single_trade(self, trade_data: dict, session: AsyncSession):
        """
        Process a single trade: calculate z-score and store.
        """
        try:
            wallet_address = trade_data.get("maker_address", "")
            trade_size_usd = float(trade_data.get("size", 0))
            
            # Filter out bot trades / small trades
            if trade_size_usd < 50:
                return

            market_id = trade_data.get("market", "")
            market_name = trade_data.get("market_name", "Unknown Market")
            timestamp = datetime.fromtimestamp(int(trade_data.get("timestamp", 0)) / 1000)

            # Skip if trade already exists (simple deduplication)
            trade_id = trade_data.get("id", "")
            from sqlalchemy import select
            existing = await session.execute(
                select(Trade).where(
                    (Trade.wallet_address == wallet_address) &
                    (Trade.market_id == market_id) &
                    (Trade.timestamp == timestamp)
                )
            )
            if existing.scalar_one_or_none():
                return

            # Calculate z-score
            z_score, is_flagged = await self.detector.calculate_z_score(
                wallet_address, trade_size_usd, session
            )

            # Create trade record
            trade = Trade(
                wallet_address=wallet_address,
                market_id=market_id,
                market_name=market_name,
                trade_size_usd=trade_size_usd,
                outcome=trade_data.get("outcome"),
                price=float(trade_data.get("price", 0)),
                timestamp=timestamp,
                is_flagged=is_flagged,
                z_score=z_score,
                is_win=trade_data.get("is_win")
            )

            session.add(trade)

            # Update trader profile if this is a flagged trade
            if is_flagged:
                await self.detector.update_trader_profile(wallet_address, session)

        except Exception as e:
            print(f"[Worker] Error processing trade: {e}")


# Global worker instance
worker_instance = None


async def get_worker() -> DataIngestionWorker:
    global worker_instance
    if worker_instance is None:
        worker_instance = DataIngestionWorker()
    return worker_instance
