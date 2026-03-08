import asyncio
import json
import hmac
import hashlib
import base64
import time
from typing import Callable, Optional, List, Dict, Any
import websockets
from websockets.exceptions import ConnectionClosed

from app.config import get_settings


class PolymarketWebSocketClient:
    """
    WebSocket client for real-time Polymarket trade updates.

    Connects to: wss://ws-subscriptions-clob.polymarket.com/ws/
    Channels:
    - market: Orderbook updates for specific tokens
    - user: Position and trade updates (requires auth)
    """

    WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    PING_INTERVAL = 10  # seconds

    def __init__(self):
        settings = get_settings()
        self.api_key = settings.polymarket_api_key.strip() if settings.polymarket_api_key else None
        self.api_secret = settings.polymarket_api_secret.strip() if settings.polymarket_api_secret else None
        self.api_passphrase = settings.polymarket_api_passphrase.strip() if settings.polymarket_api_passphrase else None

        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self.subscribed_tokens: List[str] = []
        self._message_handlers: List[Callable[[dict], None]] = []
        self._ping_task: Optional[asyncio.Task] = None
        self._listen_task: Optional[asyncio.Task] = None

    def _pad_base64(self, data: str) -> str:
        """Add padding to base64 string if needed."""
        if not data:
            return ""
        # Remove all whitespace and existing padding
        data = "".join(data.split()).rstrip('=')
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)
        return data

    def _create_auth_message(self) -> Dict[str, Any]:
        """Create authentication message for WebSocket connection."""
        if not all([self.api_key, self.api_secret, self.api_passphrase]):
            return {}

        timestamp = str(int(time.time() * 1000))
        message = timestamp + "GET" + "/ws/market"

        # Ensure proper base64 padding
        secret_padded = self._pad_base64(self.api_secret)
        try:
            secret_bytes = base64.b64decode(secret_padded)
        except Exception as e:
            print(f"[WebSocket] Auth warning: Could not decode secret ({e}).")
            return {}

        signature = hmac.new(
            secret_bytes,
            message.encode('utf-8'),
            hashlib.sha256
        ).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')

        return {
            "apiKey": self.api_key,
            "secret": self.api_secret,
            "passphrase": self.api_passphrase,
            "timestamp": timestamp,
            "signature": signature_b64,
        }

    def add_message_handler(self, handler: Callable[[dict], None]):
        """Add a handler function to process incoming messages."""
        self._message_handlers.append(handler)

    def remove_message_handler(self, handler: Callable[[dict], None]):
        """Remove a message handler."""
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)

    async def connect(self):
        """Establish WebSocket connection."""
        try:
            self.websocket = await websockets.connect(
                self.WS_URL,
                ping_interval=None,  # We handle pings manually
            )
            self.is_connected = True
            print("[WebSocket] Connected to Polymarket")

            # Start ping task
            self._ping_task = asyncio.create_task(self._ping_loop())
            # Start listen task
            self._listen_task = asyncio.create_task(self._listen_loop())

        except Exception as e:
            print(f"[WebSocket] Connection error: {e}")
            self.is_connected = False

    async def disconnect(self):
        """Close WebSocket connection."""
        self.is_connected = False

        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass

        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        if self.websocket:
            await self.websocket.close()
            print("[WebSocket] Disconnected from Polymarket")

    async def subscribe_to_market(self, token_ids: List[str]):
        """
        Subscribe to market channel for specific token IDs.
        Receives orderbook updates for these tokens.
        """
        if not self.is_connected or not self.websocket:
            print("[WebSocket] Not connected, cannot subscribe")
            return

        for token_id in token_ids:
            if token_id not in self.subscribed_tokens:
                message = {
                    "type": "subscribe",
                    "channel": "market",
                    "assets_ids": [token_id],
                }
                await self.websocket.send(json.dumps(message))
                self.subscribed_tokens.append(token_id)
                print(f"[WebSocket] Subscribed to market: {token_id[:16]}...")

    async def subscribe_to_user(self):
        """
        Subscribe to user channel for trade updates.
        Requires authentication.
        """
        if not self.is_connected or not self.websocket:
            print("[WebSocket] Not connected, cannot subscribe")
            return

        auth = self._create_auth_message()
        if not auth:
            print("[WebSocket] Authentication required for user channel")
            return

        message = {
            "type": "subscribe",
            "channel": "user",
            "auth": auth,
        }
        await self.websocket.send(json.dumps(message))
        print("[WebSocket] Subscribed to user channel")

    async def unsubscribe_from_market(self, token_ids: List[str]):
        """Unsubscribe from market updates for specific tokens."""
        if not self.is_connected or not self.websocket:
            return

        for token_id in token_ids:
            if token_id in self.subscribed_tokens:
                message = {
                    "type": "unsubscribe",
                    "channel": "market",
                    "assets_ids": [token_id],
                }
                await self.websocket.send(json.dumps(message))
                self.subscribed_tokens.remove(token_id)

    async def _ping_loop(self):
        """Send periodic ping messages to keep connection alive."""
        while self.is_connected:
            try:
                if self.websocket:
                    await self.websocket.send(json.dumps({"type": "PING"}))
                await asyncio.sleep(self.PING_INTERVAL)
            except Exception as e:
                print(f"[WebSocket] Ping error: {e}")
                break

    async def _listen_loop(self):
        """Listen for incoming WebSocket messages."""
        while self.is_connected:
            try:
                if self.websocket:
                    message = await self.websocket.recv()
                    if not message:
                        await asyncio.sleep(0.1)
                        continue

                    try:
                        data = json.loads(message)
                    except json.JSONDecodeError:
                        # Ignore binary or non-JSON messages
                        continue

                    # Skip pong responses
                    if data.get("type") == "PONG":
                        continue

                    # Process message through handlers
                    for handler in self._message_handlers:
                        try:
                            handler(data)
                        except Exception as e:
                            print(f"[WebSocket] Handler error: {e}")

            except ConnectionClosed:
                print("[WebSocket] Connection closed")
                self.is_connected = False
                break
            except Exception as e:
                # Silently wait on connection errors to avoid spamming
                await asyncio.sleep(1)
                if not self.is_connected:
                    break

    async def reconnect(self):
        """Reconnect and restore subscriptions."""
        await self.disconnect()
        await asyncio.sleep(2)
        await self.connect()

        # Restore subscriptions
        if self.subscribed_tokens:
            tokens = self.subscribed_tokens.copy()
            self.subscribed_tokens = []
            await self.subscribe_to_market(tokens)


# Message type handlers for trade processing
def parse_trade_from_ws_message(message: dict) -> Optional[dict]:
    """
    Parse a WebSocket message into a trade format.
    Returns None if message is not a trade.
    """
    msg_type = message.get("type", "")

    # Market channel trade fill
    if msg_type == "trade" or "trade" in str(message.get("event", "")):
        return {
            "id": message.get("id", message.get("trade_id", "")),
            "market": message.get("market", message.get("condition_id", "")),
            "market_name": message.get("market_name", "Unknown Market"),
            "asset_id": message.get("asset_id", message.get("token_id", "")),
            "maker_address": message.get("maker", message.get("maker_address", "")),
            "taker_address": message.get("taker", message.get("taker_address", "")),
            "price": str(message.get("price", 0)),
            "side": message.get("side", "BUY"),
            "size": str(message.get("size", message.get("amount", 0))),
            "timestamp": int(message.get("timestamp", time.time() * 1000)),
            "outcome": message.get("outcome", ""),
        }

    # Order fill event
    if msg_type == "order_fill" or msg_type == "fill":
        return {
            "id": message.get("fill_id", message.get("id", "")),
            "market": message.get("market", ""),
            "market_name": message.get("market_name", "Unknown Market"),
            "asset_id": message.get("asset_id", ""),
            "maker_address": message.get("maker", ""),
            "taker_address": message.get("taker", ""),
            "price": str(message.get("price", 0)),
            "side": message.get("side", "BUY"),
            "size": str(message.get("filled_size", message.get("size", 0))),
            "timestamp": int(message.get("timestamp", time.time() * 1000)),
            "outcome": message.get("outcome", ""),
        }

    return None


# Global WebSocket client instance
_ws_client: Optional[PolymarketWebSocketClient] = None


async def get_ws_client() -> PolymarketWebSocketClient:
    """Get or create the global WebSocket client."""
    global _ws_client
    if _ws_client is None:
        _ws_client = PolymarketWebSocketClient()
    return _ws_client
