import httpx
import os
from typing import List, Optional


class PolymarketClient:
    def __init__(self):
        self.data_api_base = os.getenv("POLYMARKET_DATA_API", "https://data-api.polymarket.com")
        self.gamma_api_base = os.getenv("POLYMARKET_GAMMA_API", "https://gamma-api.polymarket.com")
        self.client = httpx.AsyncClient(timeout=10.0)

    async def get_recent_trades(self, limit: int = 1000) -> List[dict]:
        """
        Fetch recent trades from Polymarket Data API (public, no auth required).
        """
        try:
            response = await self.client.get(
                f"{self.data_api_base}/trades",
                params={"limit": limit}
            )
            response.raise_for_status()
            trades = response.json()

            # Transform to consistent format
            result = []
            for t in trades:
                result.append({
                    "id": t.get("transactionHash", ""),
                    "market": t.get("conditionId", ""),
                    "market_name": t.get("title", "Unknown"),
                    "asset_id": t.get("asset", ""),
                    "maker_address": t.get("proxyWallet", ""),
                    "price": float(t.get("price", 0)),
                    "side": t.get("side", ""),
                    "size": float(t.get("size", 0)),
                    "timestamp": int(t.get("timestamp", 0)) * 1000,  # Convert to ms
                    "outcome": t.get("outcome", ""),
                    "event_slug": t.get("eventSlug", ""),
                })
            return result
        except Exception as e:
            print(f"Error fetching trades: {e}")
            return []

    async def get_market_info(self, market_id: str) -> Optional[dict]:
        """
        Fetch market info including resolution status from Polymarket Gamma API.
        market_id should be the conditionId.
        """
        try:
            # Try to find market by conditionId
            response = await self.client.get(
                f"{self.gamma_api_base}/markets",
                params={"condition_id": market_id, "limit": 1}
            )
            response.raise_for_status()
            markets = response.json()

            if markets and len(markets) > 0:
                data = markets[0]
                return {
                    "id": market_id,
                    "question": data.get("question", ""),
                    "resolved": data.get("closed", False),
                    "resolved_outcome": data.get("outcome", data.get("winner")),
                    "end_date": data.get("endDate"),
                }
            return None
        except Exception as e:
            print(f"Error fetching market info for {market_id}: {e}")
            return None

    async def get_resolved_markets(self, limit: int = 100, offset: int = 0) -> List[dict]:
        """
        Fetch resolved/closed markets from Gamma API.
        """
        try:
            response = await self.client.get(
                f"{self.gamma_api_base}/markets",
                params={"closed": "true", "limit": limit, "offset": offset}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching resolved markets: {e}")
            return []

    async def get_user_activity(self, wallet_address: str, limit: int = 100) -> List[dict]:
        """
        Fetch user's trade activity from Polymarket Data API.
        """
        try:
            response = await self.client.get(
                f"{self.data_api_base}/activity",
                params={"user": wallet_address, "limit": limit}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching user activity: {e}")
            return []

    async def get_historical_trades(self, before_timestamp: int = None, limit: int = 500) -> List[dict]:
        """
        Fetch historical trades. Use cursor/before_timestamp for pagination.
        """
        try:
            params = {"limit": limit}
            if before_timestamp:
                params["before"] = before_timestamp

            response = await self.client.get(
                f"{self.data_api_base}/trades",
                params=params
            )
            response.raise_for_status()
            trades = response.json()

            # Transform to consistent format
            result = []
            for t in trades:
                result.append({
                    "id": t.get("transactionHash", ""),
                    "market": t.get("conditionId", ""),
                    "market_name": t.get("title", "Unknown"),
                    "asset_id": t.get("asset", ""),
                    "maker_address": t.get("proxyWallet", ""),
                    "price": float(t.get("price", 0)),
                    "side": t.get("side", ""),
                    "size": float(t.get("size", 0)),
                    "timestamp": int(t.get("timestamp", 0)) * 1000,
                    "outcome": t.get("outcome", ""),
                    "event_slug": t.get("eventSlug", ""),
                })
            return result
        except Exception as e:
            print(f"Error fetching historical trades: {e}")
            return []

    async def close(self):
        await self.client.aclose()
