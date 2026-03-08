import asyncio
import logging
import os
from typing import List
from app.core.database import TrackedMarket
from app.domains.ingestion.snapshot_service import SnapshotService

logger = logging.getLogger(__name__)

class SnapshotWorker:
    """
    Background worker that collects order book snapshots and price history
    for tracked markets at regular intervals. Used for backtesting.
    """

    def __init__(self):
        self.snapshot_interval = int(os.getenv("SNAPSHOT_INTERVAL_SECONDS", "300"))
        self.max_markets_per_cycle = int(os.getenv("MAX_SNAPSHOT_MARKETS", "50"))
        self.is_running = False
        self.snapshot_service = SnapshotService()

    async def start(self):
        self.is_running = True
        logger.info(f"[SnapshotWorker] Starting (interval: {self.snapshot_interval}s)")

        while self.is_running:
            try:
                await self.snapshot_service.collect_snapshots(self.max_markets_per_cycle)
                await asyncio.sleep(self.snapshot_interval)
            except Exception as e:
                logger.error(f"[SnapshotWorker] Error in snapshot loop: {e}")
                await asyncio.sleep(30)

    async def stop(self):
        self.is_running = False
        await self.snapshot_service.client.close()
        logger.info("[SnapshotWorker] Stopped")

    async def add_tracked_market(self, *args, **kwargs) -> TrackedMarket:
        return await self.snapshot_service.add_tracked_market(*args, **kwargs)

    async def auto_discover_markets(self, *args, **kwargs) -> List[TrackedMarket]:
        return await self.snapshot_service.auto_discover_markets(*args, **kwargs)

    async def backfill_price_history(self, *args, **kwargs) -> int:
        return await self.snapshot_service.backfill_price_history(*args, **kwargs)


snapshot_worker_instance = None

async def get_snapshot_worker() -> SnapshotWorker:
    global snapshot_worker_instance
    if snapshot_worker_instance is None:
        snapshot_worker_instance = SnapshotWorker()
    return snapshot_worker_instance
