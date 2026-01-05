from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./polyedge.db")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, index=True, nullable=False)
    market_id = Column(String, index=True, nullable=False)
    market_name = Column(String, nullable=False)
    trade_size_usd = Column(Float, nullable=False)
    outcome = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    is_flagged = Column(Boolean, default=False)
    z_score = Column(Float, nullable=True)


class TraderProfile(Base):
    __tablename__ = "trader_profiles"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    total_trades = Column(Integer, default=0)
    avg_bet_size = Column(Float, default=0.0)
    std_bet_size = Column(Float, default=0.0)
    max_bet_size = Column(Float, default=0.0)
    total_volume = Column(Float, default=0.0)
    insider_score = Column(Float, default=0.0)  # 0-100
    last_updated = Column(DateTime, default=datetime.utcnow)
    flagged_trades_count = Column(Integer, default=0)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
