from typing import List, Optional
from datetime import datetime
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.markets.repository import MarketRepository
from app.domains.traders.schema import (
    MarketWatchItem,
    TradeResponse,
    TrackedMarketResponse,
    TrackedMarketCreate,
    DiscoverMarketsRequest,
    MarketSnapshotResponse,
    PriceHistoryResponse,
    BackfillRequest
)

class MarketService:
    def __init__(self):
        self.market_repo = MarketRepository()

    async def get_market_watch(
        self, session: AsyncSession, category: Optional[str], sort_by: str, sort_order: str, limit: int
    ) -> List[MarketWatchItem]:
        markets = await self.market_repo.get_market_watch(session, category, sort_by, sort_order, limit)
        return [MarketWatchItem.model_validate(market) for market in markets]

    async def get_market_trades(
        self, session: AsyncSession, market_id: str, page: int, limit: int
    ) -> List[TradeResponse]:
        offset = (page - 1) * limit
        trades = await self.market_repo.get_market_trades(session, market_id, offset, limit)
        return [TradeResponse.model_validate(trade) for trade in trades]

    async def get_market_trades_count(self, session: AsyncSession, market_id: str) -> dict:
        count = await self.market_repo.get_market_trades_count(session, market_id)
        return {"market_id": market_id, "total_trades": count}

    async def get_tracked_markets(
        self, session: AsyncSession, category: Optional[str], active_only: bool, limit: int
    ) -> List[TrackedMarketResponse]:
        markets = await self.market_repo.get_tracked_markets(session, category, active_only, limit)
        return [TrackedMarketResponse.model_validate(m) for m in markets]

    async def add_tracked_market(self, market: TrackedMarketCreate) -> TrackedMarketResponse:
        from app.domains.ingestion.snapshot_worker import get_snapshot_worker
        worker = await get_snapshot_worker()
        tracked = await worker.add_tracked_market(
            market_id=market.market_id,
            question=market.question,
            category=market.category,
            yes_token_id=market.yes_token_id,
            no_token_id=market.no_token_id,
        )
        return TrackedMarketResponse.model_validate(tracked)

    async def discover_markets(self, request: DiscoverMarketsRequest) -> List[TrackedMarketResponse]:
        from app.domains.ingestion.snapshot_worker import get_snapshot_worker
        worker = await get_snapshot_worker()
        discovered = await worker.auto_discover_markets(
            categories=request.categories,
            min_liquidity=request.min_liquidity,
            min_volume=request.min_volume,
            limit=request.limit,
        )
        return [TrackedMarketResponse.model_validate(m) for m in discovered]

    async def remove_tracked_market(self, session: AsyncSession, market_id: str) -> dict:
        market = await self.market_repo.get_tracked_market_by_id(session, market_id)
        if not market:
            raise HTTPException(status_code=404, detail="Tracked market not found")

        market.is_active = False
        await session.commit()
        return {"message": f"Market {market_id} removed from tracking"}

    async def get_market_snapshots(
        self, session: AsyncSession, market_id: str, start_time: Optional[datetime], end_time: Optional[datetime], limit: int
    ) -> List[MarketSnapshotResponse]:
        snapshots = await self.market_repo.get_market_snapshots(session, market_id, start_time, end_time, limit)
        return [MarketSnapshotResponse.model_validate(s) for s in snapshots]

    async def get_price_history(
        self, session: AsyncSession, market_id: str, outcome: Optional[str],
        start_time: Optional[datetime], end_time: Optional[datetime], interval: Optional[str], limit: int
    ) -> List[PriceHistoryResponse]:
        history = await self.market_repo.get_price_history(session, market_id, outcome, start_time, end_time, interval, limit)
        return [PriceHistoryResponse.model_validate(h) for h in history]

    async def backfill_price_history(self, request: BackfillRequest) -> dict:
        from app.domains.ingestion.snapshot_worker import get_snapshot_worker
        worker = await get_snapshot_worker()
        count = await worker.backfill_price_history(
            market_id=request.market_id,
            token_id=request.token_id,
            outcome=request.outcome,
            interval=request.interval,
            fidelity=request.fidelity,
            days_back=request.days_back,
        )
        return {
            "message": f"Backfilled {count} price points",
            "market_id": request.market_id,
            "outcome": request.outcome,
            "days_back": request.days_back,
        }

    async def bulk_resolve_trades(self, concurrency: int) -> dict:
        from app.domains.ingestion.resolution_worker import get_resolution_worker
        from app.domains.ingestion.insider_detector import InsiderDetector
        from app.core.database import get_db_session

        worker = await get_resolution_worker()
        stats = await worker.bulk_resolve_all(concurrency=concurrency)

        if stats["trades_resolved"] > 0:
            detector = InsiderDetector()
            async with get_db_session(readonly=True) as session:
                wallets = await self.market_repo.get_distinct_wallets_with_resolved_trades(session)

            recalculated = 0
            async with get_db_session() as session:
                for wallet in wallets:
                    await detector.update_trader_profile(wallet, session)
                    recalculated += 1

            stats["profiles_recalculated"] = recalculated

        return stats

    async def backfill_trades(self, max_pages: int, market_ids: Optional[List[str]]) -> dict:
        from app.domains.ingestion.data_worker import run_backfill
        # target_markets = set(market_ids) if market_ids else None
        
        # run_backfill could take target_markets but route currently only does max_pages
        new_trades = await run_backfill(max_pages=max_pages)

        return {
            "message": "Backfill complete",
            "new_trades_ingested": new_trades,
            "max_pages_requested": max_pages,
        }

    async def get_backtesting_stats(self, session: AsyncSession) -> dict:
        return await self.market_repo.get_backtesting_stats(session)
