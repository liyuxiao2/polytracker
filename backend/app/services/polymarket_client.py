import httpx
import random
from datetime import datetime
from typing import List, Optional

from app.schemas.trader import PolymarketTradeEvent
from app.config import get_settings


class PolymarketClient:
    def __init__(self):
        settings = get_settings()
        self.clob_api_base = settings.polymarket_clob_api
        self.data_api_base = settings.polymarket_data_api
        self.mock_mode = settings.mock_mode
        self.client = httpx.AsyncClient(timeout=30.0)

    async def get_recent_trades(self, limit: int = 100) -> List[dict]:
        """
        Fetch recent trades from Polymarket CLOB API.
        In mock mode, generates synthetic data.
        """
        if self.mock_mode:
            return self._generate_mock_trades(limit)

        try:
            response = await self.client.get(f"{self.clob_api_base}/trades", params={"limit": limit})
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching trades: {e}")
            return []

    async def get_market_activity(self, market_id: Optional[str] = None) -> List[dict]:
        """
        Fetch market activity from Polymarket Data API.
        """
        if self.mock_mode:
            return self._generate_mock_activity()

        try:
            url = f"{self.data_api_base}/activity"
            params = {"market_id": market_id} if market_id else {}
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching activity: {e}")
            return []

    def _generate_mock_trades(self, count: int = 50) -> List[dict]:
        """
        Generate mock trade data for development.
        """
        markets = [
            {"id": "mkt_1", "name": "Will Bitcoin reach $100k in 2026?"},
            {"id": "mkt_2", "name": "Will Trump win 2028 election?"},
            {"id": "mkt_3", "name": "Will AI achieve AGI by 2030?"},
            {"id": "mkt_4", "name": "Will Ethereum flip Bitcoin?"},
            {"id": "mkt_5", "name": "Will SpaceX land on Mars by 2030?"},
        ]

        wallets = [
            f"0x{''.join(random.choices('0123456789abcdef', k=40))}"
            for _ in range(20)
        ]

        trades = []
        now = datetime.utcnow()

        for i in range(count):
            market = random.choice(markets)
            wallet = random.choice(wallets)

            # Create some "whale" wallets with occasional huge bets
            is_whale = wallet in wallets[:5]
            base_size = random.uniform(100, 2000)

            if is_whale and random.random() < 0.3:  # 30% chance of large bet
                trade_size = random.uniform(10000, 50000)
            else:
                trade_size = base_size

            trade = {
                "id": f"trade_{i}",
                "market": market["id"],
                "market_name": market["name"],
                "asset_id": f"asset_{market['id']}",
                "maker_address": wallet,
                "taker_address": random.choice(wallets),
                "price": str(round(random.uniform(0.1, 0.9), 2)),
                "side": random.choice(["BUY", "SELL"]),
                "size": str(trade_size),
                "timestamp": int((now.timestamp() - random.randint(0, 86400)) * 1000),
                "outcome": random.choice(["YES", "NO"])
            }
            trades.append(trade)

        return sorted(trades, key=lambda x: x["timestamp"], reverse=True)

    def _generate_mock_activity(self, count: int = 30) -> List[dict]:
        """
        Generate mock activity data.
        """
        return []  # Can be expanded if needed

    async def close(self):
        await self.client.aclose()
