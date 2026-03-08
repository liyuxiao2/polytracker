from typing import List, Optional
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.domains.traders.repository import TraderRepository
from app.domains.traders.schema import TraderListItem, TrendingTrade, TraderProfileResponse, TradeResponse
from app.domains.ingestion.insider_detector import InsiderDetector
from datetime import datetime, timedelta

class TraderService:
    def __init__(self):
        self.trader_repo = TraderRepository()
        self.detector = InsiderDetector()

    async def get_flagged_traders(self, session: AsyncSession, limit: int, min_score: float) -> List[TraderListItem]:
        rows = await self.trader_repo.get_flagged_traders(session, min_score, limit)
        
        traders_list = []
        for profile, last_trade_time in rows:
            traders_list.append(TraderListItem(
                wallet_address=profile.wallet_address,
                insider_score=profile.insider_score,
                total_trades=profile.total_trades,
                avg_bet_size=profile.avg_bet_size,
                win_rate=profile.win_rate,
                total_pnl=profile.total_pnl,
                flagged_trades_count=profile.flagged_trades_count,
                flagged_wins_count=profile.flagged_wins_count,
                last_trade_time=last_trade_time
            ))
            
        return traders_list

    async def get_trending_trades(
        self, session: AsyncSession, min_size: float, hours: int, page: int, limit: int, sort_by: str, sort_order: str
    ) -> List[TrendingTrade]:
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        offset = (page - 1) * limit
        
        rows = await self.trader_repo.get_trending_trades(
            session, min_size, cutoff_time, sort_by, sort_order, offset, limit
        )
        
        trending = []
        for trade, profile in rows:
            deviation_pct = 0.0
            if profile and profile.avg_bet_size > 0:
                 deviation_pct = ((trade.trade_size_usd - profile.avg_bet_size) / profile.avg_bet_size) * 100

            trending.append(TrendingTrade(
                wallet_address=trade.wallet_address,
                market_name=trade.market_name,
                trade_size_usd=trade.trade_size_usd,
                z_score=trade.z_score or 0.0,
                timestamp=trade.timestamp,
                deviation_percentage=deviation_pct,
                is_win=trade.is_win,
                flag_reason=trade.flag_reason,
                outcome=trade.outcome,
                side=trade.side,
                price=trade.price,
                pnl_usd=trade.pnl_usd,
                hours_before_resolution=trade.hours_before_resolution,
                trade_hour_utc=trade.trade_hour_utc
            ))

        return trending

    async def get_trader_profile(self, session: AsyncSession, address: str) -> TraderProfileResponse:
        profile = await self.trader_repo.get_trader_by_address(session, address)
        
        if not profile:
            await self.detector.update_trader_profile(address, session)
            profile = await self.trader_repo.get_trader_by_address(session, address)

        if not profile:
            raise HTTPException(status_code=404, detail="Trader not found")

        return TraderProfileResponse.model_validate(profile)

    async def get_trader_trades(self, session: AsyncSession, address: str, limit: int) -> List[TradeResponse]:
        trades = await self.trader_repo.get_trades_by_address(session, address, limit)
        return [TradeResponse.model_validate(trade) for trade in trades]

    async def get_trader_open_positions(self, session: AsyncSession, address: str, min_unrealized_pnl: Optional[float]) -> List[TradeResponse]:
        trades = await self.trader_repo.get_open_positions(session, address, min_unrealized_pnl)
        return [TradeResponse.model_validate(trade) for trade in trades]
