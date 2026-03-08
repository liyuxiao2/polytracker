from typing import List, Tuple, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, asc, and_
from app.core.database import Trade, TraderProfile

class TraderRepository:
    """
    Repository for interacting with TraderProfile and Trade tables.
    """

    async def get_flagged_traders(
        self, session: AsyncSession, min_score: float, limit: int
    ) -> List[Tuple[TraderProfile, Optional[datetime]]]:
        last_trade_subq = (
            select(
                Trade.wallet_address,
                func.max(Trade.timestamp).label("last_trade_time")
            )
            .group_by(Trade.wallet_address)
            .subquery()
        )

        result = await session.execute(
            select(TraderProfile, last_trade_subq.c.last_trade_time)
            .outerjoin(
                last_trade_subq,
                TraderProfile.wallet_address == last_trade_subq.c.wallet_address
            )
            .where(TraderProfile.insider_score >= min_score)
            .order_by(desc(TraderProfile.insider_score))
            .limit(limit)
        )
        return list(result.all())

    async def get_trending_trades(
        self, session: AsyncSession, min_size: float, cutoff_time: datetime,
        sort_by: str, sort_order: str, offset: int, limit: int
    ) -> List[Tuple[Trade, Optional[TraderProfile]]]:
        query = select(Trade, TraderProfile).outerjoin(
            TraderProfile, Trade.wallet_address == TraderProfile.wallet_address
        ).where(
            and_(
                Trade.timestamp >= cutoff_time,
                (
                    (Trade.is_flagged == True) |
                    (Trade.trade_size_usd >= min_size) |
                    ((Trade.is_win == True) & (Trade.trade_size_usd >= 10000))
                )
            )
        )

        # Sorting
        if sort_by == "size":
            sort_col = Trade.trade_size_usd
        elif sort_by == "z_score":
            sort_col = Trade.z_score
        elif sort_by == "win_loss":
            sort_col = Trade.is_win
        elif sort_by == "deviation":
            sort_col = func.case(
                (TraderProfile.avg_bet_size > 0, (Trade.trade_size_usd - TraderProfile.avg_bet_size) / TraderProfile.avg_bet_size),
                else_=0
            )
        else: # timestamp
            sort_col = Trade.timestamp

        if sort_order == "desc":
            if sort_by == "win_loss":
                 query = query.order_by(desc(Trade.is_win).nullslast())
            else:
                 query = query.order_by(desc(sort_col))
        else:
            if sort_by == "win_loss":
                 query = query.order_by(asc(Trade.is_win).nullslast())
            else:
                query = query.order_by(asc(sort_col))

        query = query.offset(offset).limit(limit)
        result = await session.execute(query)
        return list(result.all())

    async def get_trader_by_address(
        self, session: AsyncSession, address: str
    ) -> Optional[TraderProfile]:
        result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == address)
        )
        return result.scalar_one_or_none()

    async def get_trades_by_address(
        self, session: AsyncSession, address: str, limit: int
    ) -> List[Trade]:
        result = await session.execute(
            select(Trade)
            .where(Trade.wallet_address == address)
            .order_by(desc(Trade.timestamp))
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_open_positions(
        self, session: AsyncSession, address: str, min_unrealized_pnl: Optional[float]
    ) -> List[Trade]:
        query = select(Trade).where(
            (Trade.wallet_address == address) &
            (Trade.is_win.is_(None)) &
            (Trade.unrealized_pnl_usd.isnot(None))
        ).order_by(desc(Trade.unrealized_pnl_usd))

        if min_unrealized_pnl is not None:
            query = query.where(Trade.unrealized_pnl_usd >= min_unrealized_pnl)

        result = await session.execute(query)
        return list(result.scalars().all())

    async def count_whales(self, session: AsyncSession, min_score: float = 50) -> int:
        result = await session.execute(
            select(func.count(TraderProfile.id))
            .where(TraderProfile.insider_score >= min_score)
        )
        return result.scalar() or 0

    async def count_high_signal_alerts(self, session: AsyncSession, since: datetime) -> int:
        result = await session.execute(
            select(func.count())
            .where((Trade.is_flagged == True) & (Trade.timestamp >= since))
        )
        return result.scalar() or 0

    async def count_total_trades(self, session: AsyncSession) -> int:
        result = await session.execute(select(func.count(Trade.wallet_address)))
        return result.scalar() or 0

    async def get_avg_insider_score(self, session: AsyncSession) -> float:
        result = await session.execute(select(func.avg(TraderProfile.insider_score)))
        return result.scalar() or 0.0

    async def count_resolved_trades(self, session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count())
            .where(Trade.is_win.isnot(None))
        )
        return result.scalar() or 0

    async def get_flagged_resolved_stats(self, session: AsyncSession) -> Tuple[int, int]:
        result = await session.execute(
            select(
                func.count().filter(Trade.is_win == True),
                func.count()
            )
            .where((Trade.is_flagged == True) & (Trade.is_win.isnot(None)))
        )
        row = result.one()
        return (row[0] or 0, row[1] or 0)

    async def sum_volume_since(self, session: AsyncSession, since: datetime) -> float:
        result = await session.execute(
            select(func.sum(Trade.trade_size_usd))
            .where(Trade.timestamp >= since)
        )
        return result.scalar() or 0.0

    async def sum_pnl_flagged(self, session: AsyncSession) -> float:
        result = await session.execute(
            select(func.sum(Trade.pnl_usd))
            .where((Trade.is_flagged == True) & (Trade.pnl_usd.isnot(None)))
        )
        return result.scalar() or 0.0

    async def count_open_positions(self, session: AsyncSession) -> int:
        result = await session.execute(
            select(func.count())
            .where((Trade.is_win.is_(None)) & (Trade.unrealized_pnl_usd.isnot(None)))
        )
        return result.scalar() or 0

    async def sum_total_unrealized_pnl(self, session: AsyncSession) -> float:
        result = await session.execute(
            select(func.sum(Trade.unrealized_pnl_usd))
            .where(Trade.unrealized_pnl_usd.isnot(None))
        )
        return result.scalar() or 0.0

    async def get_avg_unrealized_roi(self, session: AsyncSession) -> float:
        result = await session.execute(
            select(func.avg(TraderProfile.unrealized_roi))
            .where(TraderProfile.open_positions_count > 0)
        )
        return result.scalar() or 0.0

    async def get_trade_by_transaction_hash(
        self, session: AsyncSession, txn_hash: str
    ) -> Optional[Trade]:
        result = await session.execute(
            select(Trade).where(Trade.transaction_hash == txn_hash)
        )
        return result.scalar_one_or_none()
