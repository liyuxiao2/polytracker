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
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # YES/NO - what they bet on
    price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Entry price (0-1)
    side: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # BUY/SELL
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    # Resolution tracking
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)  # Has market resolved?
    resolved_outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # YES/NO - actual result
    is_win: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)  # Did they win?
    pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Profit/loss in USD

    # Flagging
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Why flagged
    z_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class TraderProfile(Base):
    __tablename__ = "trader_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    wallet_address: Mapped[str] = mapped_column(String, unique=True, index=True)

    # Trade counts
    total_trades: Mapped[int] = mapped_column(default=0)
    resolved_trades: Mapped[int] = mapped_column(default=0)  # Trades with known outcome
    winning_trades: Mapped[int] = mapped_column(default=0)  # Trades that won

    # Win rate (only on resolved trades)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)  # 0-1

    # Size stats
    avg_bet_size: Mapped[float] = mapped_column(Float, default=0.0)
    std_bet_size: Mapped[float] = mapped_column(Float, default=0.0)
    max_bet_size: Mapped[float] = mapped_column(Float, default=0.0)
    total_volume: Mapped[float] = mapped_column(Float, default=0.0)

    # PnL tracking
    total_pnl: Mapped[float] = mapped_column(Float, default=0.0)  # Net profit/loss

    # Insider detection
    insider_score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    flagged_trades_count: Mapped[int] = mapped_column(default=0)
    flagged_wins_count: Mapped[int] = mapped_column(default=0)  # Flagged trades that won

    last_updated: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Market(Base):
    """Track market resolution status."""
    __tablename__ = "markets"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    market_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    condition_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    question: Mapped[str] = mapped_column(String)

    # Status
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # YES/NO
    resolution_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_checked: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session
