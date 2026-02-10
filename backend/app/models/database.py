from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://polytracker:polytracker_dev_password@localhost:5432/polytracker"
)

# Create engine with appropriate settings based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite doesn't support connection pooling options
    engine = create_async_engine(DATABASE_URL, echo=False)
else:
    # PostgreSQL with optimized connection pooling
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    wallet_address = Column(String, index=True, nullable=False)
    market_id = Column(String, index=True, nullable=False)
    market_slug = Column(String, nullable=True)
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

    # Unrealized P&L tracking (for open positions)
    unrealized_pnl_usd = Column(Float, nullable=True)  # Current profit/loss if position were closed now
    current_position_value_usd = Column(Float, nullable=True)  # Current market value of position
    shares_held = Column(Float, nullable=True)  # Number of shares purchased (size/price)
    last_pnl_update = Column(DateTime, nullable=True)  # When P&L was last calculated


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
    roi = Column(Float, default=0.0)  # Return on Investment %
    profit_factor = Column(Float, default=0.0)  # Gross Win / Gross Loss
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

    # Unrealized P&L metrics (for current open positions)
    open_positions_count = Column(Integer, default=0)  # Number of unresolved trades
    total_unrealized_pnl = Column(Float, default=0.0)  # Sum of all unrealized P&L
    avg_unrealized_pnl = Column(Float, default=0.0)  # Average per open position
    unrealized_roi = Column(Float, default=0.0)  # (total_unrealized_pnl / total_open_capital) * 100
    unrealized_win_count = Column(Integer, default=0)  # Open positions with positive P&L
    unrealized_win_rate = Column(Float, default=0.0)  # % of open positions currently winning


class Market(Base):
    """Track market information and resolution status."""
    __tablename__ = "markets"

    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(String, unique=True, index=True, nullable=False)
    market_slug = Column(String, nullable=True)
    condition_id = Column(String, nullable=True)
    question = Column(String, nullable=True)
    is_resolved = Column(Boolean, default=False)
    resolved_outcome = Column(String, nullable=True)  # YES or NO
    resolution_time = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    last_checked = Column(DateTime, default=datetime.utcnow)

    # Market categorization
    category = Column(String, nullable=True)  # e.g., "NBA", "Politics", "Crypto", etc.
    tags = Column(String, nullable=True)  # Comma-separated tags

    # Market metrics
    suspicious_trades_count = Column(Integer, default=0)  # Count of flagged trades
    total_trades_count = Column(Integer, default=0)  # Total trades in this market
    total_volume = Column(Float, default=0.0)  # Total USD volume
    unique_traders_count = Column(Integer, default=0)  # Number of unique wallets

    # Volatility metrics
    current_yes_price = Column(Float, nullable=True)  # Current YES token price
    current_no_price = Column(Float, nullable=True)  # Current NO token price
    price_change_24h = Column(Float, nullable=True)  # % change in last 24h
    volatility_score = Column(Float, default=0.0)  # Standard deviation of price movements

    # Suspicious activity score (0-100)
    suspicion_score = Column(Float, default=0.0)  # Based on flagged trades, timing, etc.

    # Liquidity
    liquidity_usd = Column(Float, nullable=True)  # Total liquidity available

    # Last update timestamp for metrics
    metrics_updated_at = Column(DateTime, nullable=True)


class MarketSnapshot(Base):
    """
    Periodic snapshots of market order book state for backtesting.
    Captures bid/ask/spread/liquidity at regular intervals.
    """
    __tablename__ = "market_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    market_id = Column(String, index=True, nullable=False)  # condition_id

    # Token IDs (needed for CLOB API queries)
    yes_token_id = Column(String, nullable=True)
    no_token_id = Column(String, nullable=True)

    # YES outcome order book
    yes_best_bid = Column(Float, nullable=True)
    yes_best_ask = Column(Float, nullable=True)
    yes_spread = Column(Float, nullable=True)
    yes_bid_liquidity = Column(Float, nullable=True)  # Total size at top 5 bid levels
    yes_ask_liquidity = Column(Float, nullable=True)  # Total size at top 5 ask levels
    yes_best_bid_size = Column(Float, nullable=True)  # Size at best bid (top of book)
    yes_best_ask_size = Column(Float, nullable=True)  # Size at best ask (top of book)
    yes_mid_price = Column(Float, nullable=True)

    # NO outcome order book
    no_best_bid = Column(Float, nullable=True)
    no_best_ask = Column(Float, nullable=True)
    no_spread = Column(Float, nullable=True)
    no_bid_liquidity = Column(Float, nullable=True)
    no_ask_liquidity = Column(Float, nullable=True)
    no_best_bid_size = Column(Float, nullable=True)  # Size at best bid (top of book)
    no_best_ask_size = Column(Float, nullable=True)  # Size at best ask (top of book)
    no_mid_price = Column(Float, nullable=True)

    # Market-level metrics
    total_liquidity = Column(Float, nullable=True)
    volume_24h = Column(Float, nullable=True)

    # Composite index for efficient time-series queries
    __table_args__ = (
        # Index for querying snapshots by market and time range
        # CREATE INDEX ix_market_snapshots_market_time ON market_snapshots(market_id, timestamp)
    )


class PriceHistory(Base):
    """
    Historical price timeseries for backtesting.
    Stores price data at configurable intervals (1m, 5m, 1h, etc.)
    """
    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, index=True, nullable=False)
    market_id = Column(String, index=True, nullable=False)  # condition_id
    token_id = Column(String, index=True, nullable=False)  # CLOB token ID
    outcome = Column(String, nullable=False)  # YES or NO

    # Price data
    price = Column(Float, nullable=False)

    # Optional OHLCV data (if available)
    open_price = Column(Float, nullable=True)
    high_price = Column(Float, nullable=True)
    low_price = Column(Float, nullable=True)
    close_price = Column(Float, nullable=True)
    volume = Column(Float, nullable=True)

    # Interval indicator (e.g., '1m', '5m', '1h')
    interval = Column(String, nullable=True)

    # Composite index for efficient queries
    __table_args__ = (
        # Index for querying price history by market, outcome, and time
        # CREATE INDEX ix_price_history_market_outcome_time ON price_history(market_id, outcome, timestamp)
    )


class TrackedMarket(Base):
    """
    Markets we're actively tracking for snapshots.
    Stores token IDs and metadata for snapshot collection.
    """
    __tablename__ = "tracked_markets"

    id = Column(Integer, primary_key=True, index=True)
    market_id = Column(String, unique=True, index=True, nullable=False)  # condition_id
    question = Column(String, nullable=True)
    category = Column(String, nullable=True)  # politics, sports, crypto, etc.

    # CLOB token IDs (required for order book queries)
    yes_token_id = Column(String, nullable=True)
    no_token_id = Column(String, nullable=True)

    # Tracking config
    is_active = Column(Boolean, default=True)
    snapshot_interval_seconds = Column(Integer, default=300)  # Default 5 min

    # Market metadata
    volume = Column(Float, default=0.0)
    liquidity = Column(Float, default=0.0)
    end_date = Column(DateTime, nullable=True)
    is_closed = Column(Boolean, default=False)

    # Timestamps
    added_at = Column(DateTime, default=datetime.utcnow)
    last_snapshot_at = Column(DateTime, nullable=True)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    async with async_session_maker() as session:
        yield session
