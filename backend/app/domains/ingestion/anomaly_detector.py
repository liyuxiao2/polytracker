"""Z-score anomaly detection and trade-level flagging."""
import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.core.database import Trade
from app.core.config import get_settings


class AnomalyDetector:
    def __init__(self, z_score_threshold: float = None):
        settings = get_settings()
        self.z_score_threshold = z_score_threshold if z_score_threshold is not None else settings.insider_z_score_threshold
        self.settings = settings

    async def calculate_z_score(
        self,
        wallet_address: str,
        trade_size: float,
        session: AsyncSession
    ) -> tuple[float, bool]:
        """Calculate Z-score for a trade based on wallet's historical average."""
        result = await session.execute(
            select(Trade.trade_size_usd)
            .where(Trade.wallet_address == wallet_address)
            .order_by(Trade.timestamp.desc())
            .limit(100)
        )
        historical_trades = result.scalars().all()

        if len(historical_trades) < 3:
            return 0.0, trade_size > self.settings.large_trade_threshold

        trade_sizes = np.array(historical_trades)
        mean = np.mean(trade_sizes)
        std = np.std(trade_sizes)

        if std == 0:
            return 0.0, False

        z_score = (trade_size - mean) / std
        is_anomaly = abs(z_score) > self.z_score_threshold

        return float(z_score), is_anomaly

    async def get_trending_trades(
        self,
        session: AsyncSession,
        min_size: float = 10000,
        hours: int = 24
    ) -> list:
        """Get recent trades that are flagged or exceed minimum size."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        result = await session.execute(
            select(Trade)
            .where(
                (Trade.timestamp >= cutoff_time) &
                ((Trade.is_flagged == True) | (Trade.trade_size_usd >= min_size))
            )
            .order_by(Trade.timestamp.desc())
            .limit(100)
        )

        return result.scalars().all()

    async def detect_coordinated_trading(
        self,
        market_id: str,
        session: AsyncSession,
        window_seconds: int = 300
    ) -> list:
        """Detect potential coordinated trading activity."""
        result = await session.execute(
            select(Trade)
            .where(Trade.market_id == market_id)
            .order_by(Trade.timestamp.desc())
            .limit(100)
        )
        trades = result.scalars().all()

        if len(trades) < 2:
            return []

        coordinated_groups = []
        for i, trade in enumerate(trades):
            window_start = trade.timestamp - timedelta(seconds=window_seconds)
            window_end = trade.timestamp + timedelta(seconds=window_seconds)

            window_trades = [
                t for t in trades
                if t.transaction_hash != trade.transaction_hash
                and window_start <= t.timestamp <= window_end
                and t.wallet_address != trade.wallet_address
            ]

            if len(window_trades) >= 2:
                wallets = {trade.wallet_address} | {t.wallet_address for t in window_trades}
                coordinated_groups.append({
                    "market_id": market_id,
                    "wallets": list(wallets),
                    "trade_count": len(wallets),
                    "window_start": window_start,
                    "window_end": window_end
                })

        return coordinated_groups
