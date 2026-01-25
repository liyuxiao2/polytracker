import httpx
import os
from typing import List, Optional


class PolymarketClient:
    def __init__(self):
        self.data_api_base = os.getenv("POLYMARKET_DATA_API", "https://data-api.polymarket.com")
        self.gamma_api_base = os.getenv("POLYMARKET_GAMMA_API", "https://gamma-api.polymarket.com")
        self.clob_api_base = os.getenv("POLYMARKET_CLOB_API", "https://clob.polymarket.com")
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
        Fetch market info including resolution status from Polymarket CLOB API.
        market_id should be the conditionId.
        """
        try:
            # Use CLOB API which has more complete market data including short-term markets
            response = await self.client.get(
                f"{self.clob_api_base}/markets/{market_id}"
            )
            response.raise_for_status()
            data = response.json()

            # Determine if market is resolved by checking if it's closed and has a winner
            is_closed = data.get("closed", False)
            tokens = data.get("tokens", [])

            # Find the winning outcome from tokens
            resolved_outcome = None
            for token in tokens:
                if token.get("winner", False):
                    resolved_outcome = token.get("outcome")
                    break

            # Market is resolved if closed and has a winner
            is_resolved = is_closed and resolved_outcome is not None

            return {
                "id": market_id,
                "question": data.get("question", ""),
                "resolved": is_resolved,
                "resolved_outcome": resolved_outcome,
                "end_date": data.get("end_date_iso"),
            }
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # Market not found - try fallback to Gamma API for older markets
                return await self._get_market_info_gamma(market_id)
            print(f"Error fetching market info for {market_id}: {e}")
            return None
        except Exception as e:
            print(f"Error fetching market info for {market_id}: {e}")
            return None

    async def _get_market_info_gamma(self, market_id: str) -> Optional[dict]:
        """
        Fallback method to fetch market info from Gamma API for older markets.
        """
        try:
            response = await self.client.get(
                f"{self.gamma_api_base}/markets",
                params={"condition_id": market_id, "limit": 1}
            )
            response.raise_for_status()
            markets = response.json()

            if markets and len(markets) > 0:
                data = markets[0]
                outcome = data.get("outcome") or data.get("winner")
                is_resolved = data.get("closed", False) and outcome is not None
                return {
                    "id": market_id,
                    "question": data.get("question", ""),
                    "resolved": is_resolved,
                    "resolved_outcome": outcome,
                    "end_date": data.get("endDate"),
                }
            return None
        except Exception as e:
            print(f"Error fetching market info from Gamma API for {market_id}: {e}")
            return None

    async def get_markets_list(self, limit: int = 100, offset: int = 0, closed: bool = False) -> List[dict]:
        """
        Fetch a list of markets from Gamma API.
        Args:
            limit: Number of markets to fetch
            offset: Pagination offset
            closed: If True, fetch only closed markets; if False, fetch only active markets
        """
        try:
            params = {"limit": limit, "offset": offset}
            if closed:
                params["closed"] = "true"
            else:
                params["active"] = "true"

            response = await self.client.get(
                f"{self.gamma_api_base}/markets",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching markets list: {e}")
            return []

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
