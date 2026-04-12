import asyncio
import logging
import os

from app.domains.ingestion.data_ingestion_service import DataIngestionService

logger = logging.getLogger(__name__)


class DataIngestionWorker:
    def __init__(self):
        self.poll_interval = int(os.getenv("POLL_INTERVAL_SECONDS", "10"))
        self.is_running = False
        self.ingestion_service = DataIngestionService()
        self.client = self.ingestion_service.client  # for generic stop

    async def start(self):
        """Start the background worker that continuously polls Polymarket API."""
        self.is_running = True
        logger.info(f"[Worker] Starting data ingestion worker (poll interval: {self.poll_interval}s)")

        while self.is_running:
            try:
                await self.ingestion_service.process_trades()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"[Worker] Error in ingestion loop: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop the background worker."""
        self.is_running = False
        await self.client.close()
        logger.info("[Worker] Data ingestion worker stopped")

    async def backfill_historical_trades(
        self,
        max_pages: int = 100,
        target_market_ids: set = None,
        days_back: int = None,
        stop_on_duplicates: bool = True,
    ):
        return await self.ingestion_service.backfill_historical_trades(
            max_pages, target_market_ids, days_back, stop_on_duplicates
        )

    async def backfill_multiple_markets_parallel(self, market_ids: list[str], max_pages_per_market: int = 10000):
        return await self.ingestion_service.backfill_multiple_markets_parallel(market_ids, max_pages_per_market)

    async def backfill_multiple_markets_parallel(self, market_ids: List[str], max_pages_per_market: int = 10000):
        return await self.ingestion_service.backfill_multiple_markets_parallel(market_ids, max_pages_per_market)


worker_instance = None


async def get_worker() -> DataIngestionWorker:
    global worker_instance
    if worker_instance is None:
        worker_instance = DataIngestionWorker()
    return worker_instance


async def run_backfill(max_pages: int = 100, days_back: int = None, stop_on_duplicates: bool = True):
    worker = await get_worker()
    return await worker.backfill_historical_trades(
        max_pages=max_pages, days_back=days_back, stop_on_duplicates=stop_on_duplicates
    )
