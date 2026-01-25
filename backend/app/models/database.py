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
    outcome = Column(String, nullable=True)  # YES/NO - what they bet on
    price = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String, nullable=True)
    z_score = Column(Float, nullable=True)

    # NEW: Trade direction and type fields
    side = Column(String, nullable=True)  # BUY or SELL
    trade_type = Column(String, nullable=True)  # MARKET, LIMIT, etc.
    transaction_hash = Column(String, unique=True, index=True, nullable=True)  # Unique trade identifier
    asset_id = Column(String, nullable=True)  # Token/asset identifier

    # Resolution fields
    is_resolved = Column(Boolean, default=False)
    resolved_outcome = Column(String, nullable=True)
    is_win = Column(Boolean, nullable=True)
    pnl_usd = Column(Float, nullable=True)

    # Timing analysis fields
    hours_before_resolution = Column(Float, nullable=True)  # Hours between trade and market resolution
    trade_hour_utc = Column(Integer, nullable=True)  # Hour of day (0-23) when trade was placed


class TraderProfile(Base):
    __tablename__ = "trader_profiles"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, unique=True, index=True, nullable=False)
    total_trades = Column(Integer, default=0)
    resolved_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    win_rate = Column(Float, default=0.0)
    avg_bet_size = Column(Float, default=0.0)
    std_bet_size = Column(Float, default=0.0)
    max_bet_size = Column(Float, default=0.0)
    total_volume = Column(Float, default=0.0)
    total_pnl = Column(Float, default=0.0)
    insider_score = Column(Float, default=0.0)  # 0-100
    last_updated = Column(DateTime, default=datetime.utcnow)
    flagged_trades_count = Column(Integer, default=0)
    flagged_wins_count = Column(Integer, default=0)

    # Outcome bias tracking
    total_yes_bets = Column(Integer, default=0)
    total_no_bets = Column(Integer, default=0)
    outcome_bias = Column(Float, default=0.0)  # -1 (all NO) to +1 (all YES)

    # Buy/Sell tracking
    total_buys = Column(Integer, default=0)
    total_sells = Column(Integer, default=0)

    # NEW: Advanced insider detection fields
    first_seen = Column(DateTime, nullable=True)  # When wallet first traded
    wallet_age_days = Column(Integer, default=0)  # Days since first trade
    unique_markets_count = Column(Integer, default=0)  # Number of distinct markets traded
    market_concentration = Column(Float, default=0.0)  # 0-1, higher = more concentrated
    avg_hours_before_resolution = Column(Float, nullable=True)  # Avg timing of bets before resolution
    off_hours_trade_pct = Column(Float, default=0.0)  # % of trades during off-hours (2-6 AM UTC)
    days_since_last_trade = Column(Integer, default=0)  # Dormancy indicator
    avg_entry_price = Column(Float, nullable=True)  # Average price they enter positions at
    longshot_win_rate = Column(Float, default=0.0)  # Win rate on bets with price < 0.2
    large_bet_win_rate = Column(Float, default=0.0)  # Win rate on bets > 2x their average


class Market(Base):
    """Track market information and resolution status."""
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(String, unique=True, index=True, nullable=False)
    condition_id = Column(String, nullable=True)
    question = Column(String, nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_outcome = Column(String, nullable=True)  # YES or NO
    resolution_time = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    last_checked = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
