from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.trader_repository import TraderRepository
from app.schemas.trader import DashboardStats
from datetime import datetime, timedelta

class SystemService:
    def __init__(self):
        self.trader_repo = TraderRepository()

    async def get_dashboard_stats(self, session: AsyncSession) -> DashboardStats:
        total_whales = await self.trader_repo.count_whales(session)
        
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        alerts_today = await self.trader_repo.count_high_signal_alerts(session, today_start)
        
        total_trades = await self.trader_repo.count_total_trades(session)
        avg_score = await self.trader_repo.get_avg_insider_score(session)
        
        total_resolved = await self.trader_repo.count_resolved_trades(session)
        wins, total_flagged_resolved = await self.trader_repo.get_flagged_resolved_stats(session)
        avg_win_rate = (wins / total_flagged_resolved * 100) if total_flagged_resolved > 0 else 0.0

        cutoff_24h = datetime.utcnow() - timedelta(hours=24)
        total_volume_24h = await self.trader_repo.sum_volume_since(session, cutoff_24h)
        
        total_pnl_flagged = await self.trader_repo.sum_pnl_flagged(session)
        total_open_positions = await self.trader_repo.count_open_positions(session)
        total_unrealized_pnl = await self.trader_repo.sum_total_unrealized_pnl(session)
        avg_unrealized_roi = await self.trader_repo.get_avg_unrealized_roi(session)

        return DashboardStats(
            total_whales_tracked=total_whales,
            high_signal_alerts_today=alerts_today,
            total_trades_monitored=total_trades,
            avg_insider_score=float(avg_score),
            total_resolved_trades=total_resolved,
            avg_win_rate=float(avg_win_rate),
            total_volume_24h=float(total_volume_24h),
            total_pnl_flagged=float(total_pnl_flagged),
            total_open_positions=total_open_positions,
            total_unrealized_pnl=float(total_unrealized_pnl),
            avg_unrealized_roi=float(avg_unrealized_roi)
        )
