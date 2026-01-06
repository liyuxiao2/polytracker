import asyncio
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.database import Trade, async_session_maker
from app.services.polymarket_client import PolymarketClient
from app.services.websocket_client import (
    get_ws_client,
    parse_trade_from_ws_message,
    PolymarketWebSocketClient,
)
from app.services.insider_detector import InsiderDetector
from app.config import get_settings


class DataIngestionWorker:
    """
    Background worker that ingests trade data from Polymarket.

    Supports two modes:
    1. Polling mode: Periodically fetches trades via REST API
    2. WebSocket mode: Real-time trade streaming (when auth available)
    """

    def __init__(self):
        settings = get_settings()
        self.client = PolymarketClient()
        self.detector = InsiderDetector()
        self.poll_interval = settings.poll_interval_seconds
        self.is_running = False
        self.use_websocket = bool(settings.polymarket_api_key)
        self._ws_client: PolymarketWebSocketClient = None
        self._trade_queue: asyncio.Queue = asyncio.Queue()

    async def start(self):
        """
        Start the background worker.
        Uses WebSocket if authenticated, otherwise falls back to polling.
        """
        self.is_running = True
        settings = get_settings()

        if not settings.mock_mode and self.use_websocket:
            print("[Worker] Starting in WebSocket mode (real-time)")
            try:
                await self._start_websocket_mode()
            except Exception as e:
                print(f"[Worker] WebSocket mode failed to start: {e}")
                print("[Worker] Falling back to polling mode")
                await self._start_polling_mode()
        else:
            mode = "mock" if settings.mock_mode else "polling"
            print(f"[Worker] Starting in {mode} mode (poll interval: {self.poll_interval}s)")
            await self._start_polling_mode()

    async def _start_polling_mode(self):
        """Run worker in polling mode."""
        while self.is_running:
            try:
                await self._process_trades()
                await asyncio.sleep(self.poll_interval)
            except Exception as e:
                print(f"[Worker] Error in polling loop: {e}")
                await asyncio.sleep(5)

    async def _start_websocket_mode(self):
        """Run worker in WebSocket mode with polling fallback."""
        self._ws_client = await get_ws_client()
        self._ws_client.add_message_handler(self._handle_ws_message)

        # Connect and subscribe
        await self._ws_client.connect()
        await self._ws_client.subscribe_to_user()

        # Also subscribe to top markets
        markets = await self.client.get_active_markets(limit=20)
        token_ids = []
        for market in markets:
            token_ids.extend(market.get("token_ids", []))
        if token_ids:
            await self._ws_client.subscribe_to_market(token_ids[:50])  # Limit subscriptions

        # Initial poll to populate data immediately
        print("[Worker] Running initial trade fetch...")
        await self._process_trades()

        # Process trades from queue with periodic polling backup
        poll_counter = 0
        while self.is_running:
            try:
                # Process queued trades from WebSocket
                trades_processed = 0
                while not self._trade_queue.empty():
                    trade_data = await self._trade_queue.get()
                    async with async_session_maker() as session:
                        await self._process_single_trade(trade_data, session)
                        await session.commit()
                    trades_processed += 1

                if trades_processed > 0:
                    print(f"[Worker] Processed {trades_processed} real-time trades")

                # Periodic polling every ~30 seconds as backup (WebSocket may not send all trades)
                poll_counter += 1
                if poll_counter >= 30:
                    poll_counter = 0
                    await self._process_trades()

                # Reconnect if disconnected
                if not self._ws_client.is_connected:
                    print("[Worker] WebSocket disconnected, reconnecting...")
                    await self._ws_client.reconnect()

                await asyncio.sleep(1)  # Check queue every second

            except Exception as e:
                print(f"[Worker] Error in WebSocket mode: {e}")
                await asyncio.sleep(5)

    def _handle_ws_message(self, message: dict):
        """Handle incoming WebSocket message."""
        trade = parse_trade_from_ws_message(message)
        if trade:
            # Queue trade for processing
            try:
                self._trade_queue.put_nowait(trade)
            except asyncio.QueueFull:
                print("[Worker] Trade queue full, dropping trade")

    async def stop(self):
        """Stop the background worker."""
        self.is_running = False

        if self._ws_client:
            await self._ws_client.disconnect()

        await self.client.close()
        print("[Worker] Data ingestion worker stopped")

    async def _process_trades(self):
        """Fetch trades from API, calculate z-scores, and store in database."""
        async with async_session_maker() as session:
            trades = await self.client.get_recent_trades(limit=100)
            print(f"[Worker] Fetched {len(trades)} trades from API")

            if trades and len(trades) > 0:
                sample = trades[0]
                print(f"[Worker] Sample trade: market={sample.get('market_name', 'N/A')[:30]}, addr={sample.get('maker_address', 'N/A')[:12]}...")

            processed = 0
            for trade_data in trades:
                result = await self._process_single_trade(trade_data, session)
                if result:
                    processed += 1

            await session.commit()
            print(f"[Worker] Processed {processed} new trades (fetched {len(trades)})")

    async def _process_single_trade(self, trade_data: dict, session: AsyncSession) -> bool:
        """
        Process a single trade: calculate z-score and store.
        Returns True if trade was new and processed.
        """
        try:
            wallet_address = trade_data.get("maker_address", "")
            trade_size_usd = float(trade_data.get("size", 0))
            market_id = trade_data.get("market", "")
            market_name = trade_data.get("market_name", "Unknown Market")

            # Handle timestamp (could be in ms or seconds)
            raw_timestamp = int(trade_data.get("timestamp", 0))
            if raw_timestamp > 10000000000:  # Milliseconds
                timestamp = datetime.fromtimestamp(raw_timestamp / 1000)
            else:  # Seconds
                timestamp = datetime.fromtimestamp(raw_timestamp)

            # Skip invalid trades
            if not wallet_address or wallet_address == "0x" + "0" * 40:
                return False

            # Deduplication check
            trade_id = trade_data.get("id", "")
            existing = await session.execute(
                select(Trade).where(
                    (Trade.wallet_address == wallet_address) &
                    (Trade.market_id == market_id) &
                    (Trade.timestamp == timestamp)
                )
            )
            if existing.scalar_one_or_none():
                return False

            # Calculate z-score
            z_score, is_flagged = await self.detector.calculate_z_score(
                wallet_address, trade_size_usd, session
            )

            # Create trade record
            trade = Trade(
                wallet_address=wallet_address,
                market_id=market_id,
                market_name=market_name,
                trade_size_usd=trade_size_usd,
                outcome=trade_data.get("outcome"),
                price=float(trade_data.get("price", 0)),
                side=trade_data.get("side"),
                timestamp=timestamp,
                is_resolved=False,  # Will be updated by resolution checker
                is_flagged=is_flagged,
                z_score=z_score
            )

            session.add(trade)

            # Update trader profile if this is a flagged trade
            if is_flagged:
                await self.detector.update_trader_profile(wallet_address, session)
                print(f"[Worker] Flagged trade: {wallet_address[:10]}... ${trade_size_usd:.2f} (z={z_score:.2f})")

            return True

        except Exception as e:
            print(f"[Worker] Error processing trade: {e}")
            return False


# Global worker instance
worker_instance = None


async def get_worker() -> DataIngestionWorker:
    global worker_instance
    if worker_instance is None:
        worker_instance = DataIngestionWorker()
    return worker_instance
