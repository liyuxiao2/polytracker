from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class TradeBase(BaseModel):
    wallet_address: str
    market_id: str
    market_name: str
    trade_size_usd: float
    outcome: Optional[str] = None
    price: Optional[float] = None
    timestamp: datetime


class TradeCreate(TradeBase):
    pass


class TradeResponse(TradeBase):
    id: int
    is_flagged: bool
    z_score: Optional[float] = None

    class Config:
        from_attributes = True


class TraderProfileResponse(BaseModel):
    wallet_address: str
    total_trades: int
    avg_bet_size: float
    std_bet_size: float
    max_bet_size: float
    total_volume: float
    insider_score: float = Field(ge=0, le=100)
    last_updated: datetime
    flagged_trades_count: int

    class Config:
        from_attributes = True


class TraderListItem(BaseModel):
    wallet_address: str
    insider_score: float
    total_trades: int
    avg_bet_size: float
    flagged_trades_count: int
    last_trade_time: Optional[datetime] = None


class TrendingTrade(BaseModel):
    wallet_address: str
    market_name: str
    trade_size_usd: float
    z_score: float
    timestamp: datetime
    deviation_percentage: float


class DashboardStats(BaseModel):
    total_whales_tracked: int
    high_signal_alerts_today: int
    total_trades_monitored: int
    avg_insider_score: float


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
