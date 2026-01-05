from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Float, DateTime, Boolean
from datetime import datetime
from typing import Optional, AsyncGenerator

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    wallet_address: Mapped[str] = mapped_column(String, index=True)
    market_id: Mapped[str] = mapped_column(String, index=True)
    market_name: Mapped[str] = mapped_column(String)
    trade_size_usd: Mapped[float] = mapped_column(Float)
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class TraderProfile(Base):
    __tablename__ = "trader_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    wallet_address: Mapped[str] = mapped_column(String, unique=True, index=True)
    total_trades: Mapped[int] = mapped_column(default=0)
    avg_bet_size: Mapped[float] = mapped_column(Float, default=0.0)
    std_bet_size: Mapped[float] = mapped_column(Float, default=0.0)
    max_bet_size: Mapped[float] = mapped_column(Float, default=0.0)
    total_volume: Mapped[float] = mapped_column(Float, default=0.0)
    insider_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    flagged_trades_count: Mapped[int] = mapped_column(default=0)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
