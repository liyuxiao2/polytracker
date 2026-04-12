from datetime import datetime

from sqlalchemy import asc, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Market, MarketSnapshot, PriceHistory, TrackedMarket, Trade


class MarketRepository:
    """
    Repository for interacting with Market, TrackedMarket, MarketSnapshot, and PriceHistory tables.
    """

    async def get_market_watch(
        self, session: AsyncSession, category: str | None, sort_by: str, sort_order: str, limit: int
    ) -> list[Market]:
        query = select(Market).where(Market.is_resolved == False)

        if category:
            query = query.where(Market.category == category)

        if sort_by == "suspicion_score":
            sort_col = Market.suspicion_score
        elif sort_by == "volatility_score":
            sort_col = Market.volatility_score
        elif sort_by == "total_volume":
            sort_col = Market.total_volume
        elif sort_by == "suspicious_trades_count":
            sort_col = Market.suspicious_trades_count
        else:
            sort_col = Market.suspicion_score

        if sort_order == "desc":
            query = query.order_by(desc(sort_col))
        else:
            query = query.order_by(asc(sort_col))

        query = query.limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_market_trades(self, session: AsyncSession, market_id: str, offset: int, limit: int) -> list[Trade]:
        result = await session.execute(
            select(Trade)
            .where(Trade.market_id == market_id)
            .order_by(desc(Trade.timestamp))
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_market_trades_count(self, session: AsyncSession, market_id: str) -> int:
        result = await session.execute(select(func.count()).where(Trade.market_id == market_id))
        return result.scalar() or 0

    async def get_tracked_markets(
        self, session: AsyncSession, category: str | None, active_only: bool, limit: int
    ) -> list[TrackedMarket]:
        query = select(TrackedMarket)

        if active_only:
            query = query.where(TrackedMarket.is_active == True)

        if category:
            query = query.where(TrackedMarket.category == category)

        query = query.order_by(desc(TrackedMarket.liquidity)).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_tracked_market_by_id(self, session: AsyncSession, market_id: str) -> TrackedMarket | None:
        result = await session.execute(select(TrackedMarket).where(TrackedMarket.market_id == market_id))
        return result.scalar_one_or_none()

    async def get_market_snapshots(
        self,
        session: AsyncSession,
        market_id: str,
        start_time: datetime | None,
        end_time: datetime | None,
        limit: int,
    ) -> list[MarketSnapshot]:
        query = select(MarketSnapshot).where(MarketSnapshot.market_id == market_id)

        if start_time:
            query = query.where(MarketSnapshot.timestamp >= start_time)
        if end_time:
            query = query.where(MarketSnapshot.timestamp <= end_time)

        query = query.order_by(MarketSnapshot.timestamp).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_price_history(
        self,
        session: AsyncSession,
        market_id: str,
        outcome: str | None,
        start_time: datetime | None,
        end_time: datetime | None,
        interval: str | None,
        limit: int,
    ) -> list[PriceHistory]:
        query = select(PriceHistory).where(PriceHistory.market_id == market_id)

        if outcome:
            query = query.where(PriceHistory.outcome == outcome.upper())
        if start_time:
            query = query.where(PriceHistory.timestamp >= start_time)
        if end_time:
            query = query.where(PriceHistory.timestamp <= end_time)
        if interval:
            query = query.where(PriceHistory.interval == interval)

        query = query.order_by(PriceHistory.timestamp).limit(limit)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_distinct_wallets_with_resolved_trades(self, session: AsyncSession) -> list[str]:
        result = await session.execute(select(Trade.wallet_address).where(Trade.is_resolved == True).distinct())
        return [row[0] for row in result.all()]

    async def get_backtesting_stats(self, session: AsyncSession) -> dict:
        tracked_result = await session.execute(
            select(func.count(TrackedMarket.id)).where(TrackedMarket.is_active == True)
        )
        tracked_count = tracked_result.scalar() or 0

        snapshot_result = await session.execute(select(func.count(MarketSnapshot.id)))
        snapshot_count = snapshot_result.scalar() or 0

        price_result = await session.execute(select(func.count(PriceHistory.id)))
        price_count = price_result.scalar() or 0

        oldest_snapshot = await session.execute(select(func.min(MarketSnapshot.timestamp)))
        oldest_ts = oldest_snapshot.scalar()

        newest_snapshot = await session.execute(select(func.max(MarketSnapshot.timestamp)))
        newest_ts = newest_snapshot.scalar()

        return {
            "tracked_markets": tracked_count,
            "total_snapshots": snapshot_count,
            "total_price_points": price_count,
            "data_range": {
                "oldest": oldest_ts,
                "newest": newest_ts,
            },
        }

    async def get_active_tracked_markets(self, session: AsyncSession, limit: int) -> list[TrackedMarket]:
        result = await session.execute(
            select(TrackedMarket)
            .where(TrackedMarket.is_active == True)
            .where(TrackedMarket.is_closed == False)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_price_history_record(
        self, session: AsyncSession, market_id: str, token_id: str, ts: datetime
    ) -> PriceHistory | None:
        from sqlalchemy import and_

        result = await session.execute(
            select(PriceHistory).where(
                and_(
                    PriceHistory.market_id == market_id, PriceHistory.token_id == token_id, PriceHistory.timestamp == ts
                )
            )
        )
        return result.scalar_one_or_none()
