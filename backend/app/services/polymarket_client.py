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
                params["closed"] = "false"

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

    async def get_price_history(
        self,
        token_id: str,
        interval: str = "1d",
        fidelity: int = 60,
        start_ts: int = None,
        end_ts: int = None
    ) -> List[dict]:
        """
        Fetch historical price data for a token from CLOB API.

        Args:
            token_id: The CLOB token ID (not condition_id - each outcome has its own token)
            interval: Duration - '1m', '1h', '6h', '1d', '1w', 'max' (mutually exclusive with start_ts/end_ts)
            fidelity: Resolution in minutes (e.g., 5 = 5-minute candles)
            start_ts: Unix timestamp for start of range (optional, use instead of interval)
            end_ts: Unix timestamp for end of range (optional, use instead of interval)

        Returns:
            List of {timestamp, price} dicts
        """
        try:
            params = {"market": token_id}

            if start_ts and end_ts:
                params["startTs"] = start_ts
                params["endTs"] = end_ts
            else:
                params["interval"] = interval

            if fidelity:
                params["fidelity"] = fidelity

            response = await self.client.get(
                f"{self.clob_api_base}/prices-history",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            history = data.get("history", [])
            return [{"timestamp": h["t"], "price": h["p"]} for h in history]
        except Exception as e:
            print(f"Error fetching price history for {token_id}: {e}")
            return []

    async def get_order_book(self, token_id: str) -> Optional[dict]:
        """
        Fetch the full order book for a token from CLOB API.

        Args:
            token_id: The CLOB token ID

        Returns:
            Dict with 'bids' and 'asks' arrays, each containing {price, size} entries
        """
        try:
            response = await self.client.get(
                f"{self.clob_api_base}/book",
                params={"token_id": token_id}
            )
            response.raise_for_status()
            data = response.json()

            # Parse bids and asks
            bids = []
            asks = []

            for bid in data.get("bids", []):
                bids.append({
                    "price": float(bid.get("price", 0)),
                    "size": float(bid.get("size", 0))
                })

            for ask in data.get("asks", []):
                asks.append({
                    "price": float(ask.get("price", 0)),
                    "size": float(ask.get("size", 0))
                })

            # Sort: bids descending by price, asks ascending by price
            bids.sort(key=lambda x: x["price"], reverse=True)
            asks.sort(key=lambda x: x["price"])

            # Calculate best bid/ask and spread
            best_bid = bids[0]["price"] if bids else 0
            best_ask = asks[0]["price"] if asks else 1
            spread = best_ask - best_bid if bids and asks else None

            # Calculate total liquidity at top of book
            bid_liquidity = sum(b["size"] for b in bids[:5]) if bids else 0
            ask_liquidity = sum(a["size"] for a in asks[:5]) if asks else 0

            return {
                "token_id": token_id,
                "bids": bids,
                "asks": asks,
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": spread,
                "bid_liquidity": bid_liquidity,
                "ask_liquidity": ask_liquidity,
                "mid_price": (best_bid + best_ask) / 2 if bids and asks else None
            }
        except Exception as e:
            print(f"Error fetching order book for {token_id}: {e}")
            return None

    async def get_midpoint(self, token_id: str) -> Optional[float]:
        """
        Fetch the midpoint price for a token.
        """
        try:
            response = await self.client.get(
                f"{self.clob_api_base}/midpoint",
                params={"token_id": token_id}
            )
            response.raise_for_status()
            data = response.json()
            return float(data.get("mid", 0))
        except Exception as e:
            print(f"Error fetching midpoint for {token_id}: {e}")
            return None

    async def get_spread(self, token_id: str) -> Optional[dict]:
        """
        Fetch current spread data (best bid/ask) for a token.
        """
        try:
            response = await self.client.get(
                f"{self.clob_api_base}/spread",
                params={"token_id": token_id}
            )
            response.raise_for_status()
            data = response.json()

            bid = float(data.get("bid", 0))
            ask = float(data.get("ask", 0))

            return {
                "token_id": token_id,
                "bid": bid,
                "ask": ask,
                "spread": ask - bid if bid and ask else None
            }
        except Exception as e:
            print(f"Error fetching spread for {token_id}: {e}")
            return None

    async def get_markets_clob(self, next_cursor: str = None) -> dict:
        """
        Fetch markets from CLOB API with token IDs for order book queries.
        Returns markets with their YES/NO token IDs.
        """
        try:
            params = {}
            if next_cursor:
                params["next_cursor"] = next_cursor

            response = await self.client.get(
                f"{self.clob_api_base}/markets",
                params=params
            )
            response.raise_for_status()
            data = response.json()

            markets = []
            for m in data.get("data", data) if isinstance(data, dict) else data:
                tokens = m.get("tokens", [])
                yes_token = None
                no_token = None

                for token in tokens:
                    if token.get("outcome", "").upper() == "YES":
                        yes_token = token.get("token_id")
                    elif token.get("outcome", "").upper() == "NO":
                        no_token = token.get("token_id")

                markets.append({
                    "condition_id": m.get("condition_id"),
                    "question": m.get("question", ""),
                    "market_slug": m.get("market_slug", ""),
                    "yes_token_id": yes_token,
                    "no_token_id": no_token,
                    "active": m.get("active", False),
                    "closed": m.get("closed", False),
                    "volume": float(m.get("volume", 0) or 0),
                    "liquidity": float(m.get("liquidity", 0) or 0),
                })

            return {
                "markets": markets,
                "next_cursor": data.get("next_cursor") if isinstance(data, dict) else None
            }
        except Exception as e:
            print(f"Error fetching CLOB markets: {e}")
            return {"markets": [], "next_cursor": None}

    async def close(self):
        await self.client.aclose()
