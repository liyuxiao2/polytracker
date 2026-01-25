from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TradeBase(BaseModel):
    wallet_address: str
    market_id: str
    market_name: str
    trade_size_usd: float
    outcome: Optional[str] = None  # YES or NO
    price: Optional[float] = None
    timestamp: datetime
    side: Optional[str] = None  # BUY or SELL
    trade_type: Optional[str] = None  # MARKET, LIMIT, etc.


class TradeCreate(TradeBase):
    transaction_hash: Optional[str] = None
    asset_id: Optional[str] = None


class TradeResponse(TradeBase):
    id: int
    is_flagged: bool
    flag_reason: Optional[str] = None
    z_score: Optional[float] = None
    is_win: Optional[bool] = None
    pnl_usd: Optional[float] = None
    transaction_hash: Optional[str] = None

    class Config:
        from_attributes = True


class TraderProfileResponse(BaseModel):
    wallet_address: str
    total_trades: int
    resolved_trades: int = 0
    winning_trades: int = 0
    win_rate: float = 0.0
    avg_bet_size: float
    std_bet_size: float
    max_bet_size: float
    total_volume: float
    total_pnl: float = 0.0
    insider_score: float = Field(ge=0, le=100)
    last_updated: datetime
    flagged_trades_count: int
    flagged_wins_count: int = 0
    # Outcome bias tracking
    total_yes_bets: int = 0
    total_no_bets: int = 0
    outcome_bias: float = 0.0  # -1 (all NO) to +1 (all YES)
    # Buy/Sell tracking
    total_buys: int = 0
    total_sells: int = 0
    # Advanced insider detection signals
    first_seen: Optional[datetime] = None
    wallet_age_days: int = 0
    unique_markets_count: int = 0
    market_concentration: float = 0.0  # HHI score (0-1, higher = more concentrated)
    avg_hours_before_resolution: Optional[float] = None
    off_hours_trade_pct: float = 0.0  # % of trades during 2-6 AM UTC
    days_since_last_trade: int = 0
    avg_entry_price: Optional[float] = None
    longshot_win_rate: float = 0.0  # Win rate on < 20% odds bets
    large_bet_win_rate: float = 0.0  # Win rate on bets > 2x average

    class Config:
        from_attributes = True


class TraderListItem(BaseModel):
    wallet_address: str
    insider_score: float
    total_trades: int
    avg_bet_size: float
    win_rate: float = 0.0
    total_pnl: float = 0.0
    flagged_trades_count: int
    flagged_wins_count: int = 0
    last_trade_time: Optional[datetime] = None


class TrendingTrade(BaseModel):
    wallet_address: str
    market_name: str
    trade_size_usd: float
    z_score: float
    timestamp: datetime
    deviation_percentage: float
    is_win: Optional[bool] = None
    flag_reason: Optional[str] = None
    # Trade details
    outcome: Optional[str] = None  # YES or NO
    side: Optional[str] = None  # BUY or SELL
    price: Optional[float] = None
    pnl_usd: Optional[float] = None
    # Timing analysis
    hours_before_resolution: Optional[float] = None
    trade_hour_utc: Optional[int] = None


class DashboardStats(BaseModel):
    total_whales_tracked: int
    high_signal_alerts_today: int
    total_trades_monitored: int
    avg_insider_score: float
    total_resolved_trades: int
    avg_win_rate: float
    # NEW stats
    total_volume_24h: float = 0.0
    total_pnl_flagged: float = 0.0


class PolymarketTradeEvent(BaseModel):
    """Schema for Polymarket CLOB API trade event"""
    id: str
    market: str
    asset_id: str
    maker_address: str
    taker_address: Optional[str] = None
    price: str
    side: str
    size: str
    timestamp: int
    outcome: Optional[str] = None


class PolymarketActivityEvent(BaseModel):
    """Schema for Polymarket Data API activity"""
    user: str
    market_id: str
    market_name: str
    outcome: str
    amount: float
    price: float
    timestamp: int
