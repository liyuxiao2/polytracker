import logging
from typing import Optional, List
from datetime import datetime, timedelta
import asyncio
import uuid
import os
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import Trade, async_session_maker
from app.domains.traders.repository import TraderRepository
from app.domains.ingestion.polymarket_client import PolymarketClient
from app.domains.ingestion.insider_detector import InsiderDetector
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class DataIngestionService:
    def __init__(self):
        self.trader_repo = TraderRepository()
        self.client = PolymarketClient()
        self.detector = InsiderDetector()
        self.min_trade_size = float(os.getenv("MIN_TRADE_SIZE_USD", "0"))
        self.trade_fetch_limit = int(os.getenv("TRADE_FETCH_LIMIT", "1000"))

        # Load tracked markets from configuration
        self.settings = get_settings()
        self.tracked_markets = set(self.settings.tracked_market_id_list)

        if self.tracked_markets:
            logger.info(f"[Ingestion] Tracking {len(self.tracked_markets)} specific markets: {list(self.tracked_markets)}")
        else:
            logger.info(f"[Ingestion] Tracking ALL markets (no filter configured)")

    async def process_trades(self) -> dict:
        import time
        start_time = time.time()
        new_trades = 0
        flagged_trades = 0

        async with async_session_maker() as session:
            trades = await self.client.get_recent_trades(limit=self.trade_fetch_limit)
            fetch_time = time.time() - start_time

            for trade_data in trades:
                result = await self.process_single_trade(trade_data, session)
                if result:
                    new_trades += 1
                    if result.is_flagged:
                        flagged_trades += 1

            await session.commit()
            total_time = time.time() - start_time
            if new_trades > 0:
                logger.info(f"[Ingestion] Ingested {new_trades} new trades ({flagged_trades} flagged) [fetch: {fetch_time:.1f}s, total: {total_time:.1f}s]")
                
        return {"new_trades": new_trades, "flagged_trades": flagged_trades}

    async def process_single_trade(self, trade_data: dict, session: AsyncSession) -> Optional[Trade]:
        try:
            # Filter by tracked markets if configured
            market_id = trade_data.get("market", "")
            if self.tracked_markets and market_id not in self.tracked_markets:
                return None  # Skip trades from non-tracked markets

            wallet_address = trade_data.get("maker_address", "")
            trade_size_usd = float(trade_data.get("size", 0))

            if self.min_trade_size > 0 and trade_size_usd < self.min_trade_size:
                return None

            transaction_hash = trade_data.get("id", "") or f"unknown_{uuid.uuid4().hex[:16]}"

            if transaction_hash:
                existing = await self.trader_repo.get_trade_by_transaction_hash(session, transaction_hash)
                if existing:
                    return None
            market_slug = trade_data.get("event_slug", "")
            market_name = trade_data.get("market_name", "Unknown Market")
            timestamp = datetime.fromtimestamp(int(trade_data.get("timestamp", 0)) / 1000)
            side = trade_data.get("side", "").upper()
            if side not in ("BUY", "SELL"):
                side = None

            outcome = trade_data.get("outcome", "")
            price = float(trade_data.get("price", 0))
            asset_id = trade_data.get("asset_id", "")

            z_score, is_flagged = await self.detector.calculate_z_score(
                wallet_address, trade_size_usd, session,
                tracked_markets=self.tracked_markets
            )

            flag_reason = None
            if is_flagged:
                if z_score > 0:
                    flag_reason = f"Unusually large bet (z-score: {z_score:.2f})"
                else:
                    flag_reason = f"Unusually small bet (z-score: {z_score:.2f})"

            trade = Trade(
                wallet_address=wallet_address,
                market_id=market_id,
                market_slug=market_slug,
                market_name=market_name,
                trade_size_usd=trade_size_usd,
                outcome=outcome,
                price=price,
                timestamp=timestamp,
                is_flagged=is_flagged,
                flag_reason=flag_reason,
                z_score=z_score,
                side=side,
                trade_type=None,
                transaction_hash=transaction_hash,
                asset_id=asset_id if asset_id else None,
                trade_hour_utc=timestamp.hour,
            )

            session.add(trade)

            if is_flagged:
                profile = await self.detector.update_trader_profile(
                    wallet_address, session,
                    tracked_markets=self.tracked_markets
                )
                if profile and profile.total_trades < 50:
                    asyncio.create_task(self.backfill_trader_history(wallet_address))

            return trade

        except Exception as e:
            logger.error(f"[Ingestion] Error processing trade: {e}")
            return None

    async def backfill_trader_history(self, wallet_address: str):
        logger.info(f"[Ingestion] Backfilling history for {wallet_address}...")
        try:
            activity = await self.client.get_user_activity(wallet_address, limit=500)
            if not activity:
                return

            async with async_session_maker() as session:
                count = 0
                for item in activity:
                    txn_hash = item.get("transactionHash")
                    if not txn_hash:
                        continue
                        
                    existing = await self.trader_repo.get_trade_by_transaction_hash(session, txn_hash)
                    if existing:
                        continue
                        
                    market_id = item.get("conditionId") or ""
                    if item.get("type", "").upper() not in ("TRADE", "ERC1155_TRANSFER", "CTF_TRADE"):
                        continue
                        
                    price = float(item.get("price", 0))
                    size = float(item.get("usdcSize", 0))
                    
                    if self.min_trade_size > 0 and size < self.min_trade_size:
                        continue
                        
                    timestamp = datetime.fromtimestamp(int(item.get("timestamp", 0)))
                    
                    trade = Trade(
                        wallet_address=wallet_address,
                        market_id=market_id,
                        market_name=item.get("title") or "Backfilled Trade",
                        market_slug=item.get("eventSlug"),
                        trade_size_usd=size,
                        outcome=item.get("outcome"),
                        price=price,
                        timestamp=timestamp,
                        is_flagged=False,
                        side=item.get("side", "").upper(),
                        transaction_hash=txn_hash,
                        trade_hour_utc=timestamp.hour
                    )
                    
                    session.add(trade)
                    count += 1
                
                await session.commit()
                if count > 0:
                    logger.info(f"[Ingestion] Backfilled {count} trades for {wallet_address}")
                    await self.detector.update_trader_profile(
                        wallet_address, session,
                        tracked_markets=self.tracked_markets
                    )
                    
        except Exception as e:
            logger.error(f"[Ingestion] Error backfilling {wallet_address}: {e}")

    async def backfill_historical_trades(
        self,
        max_pages: int = 100,
        target_market_ids: set = None,
        days_back: int = None,
        stop_on_duplicates: bool = True
    ):
        logger.info(f"[Backfill] Starting historical trade backfill (max {max_pages} pages, days_back={days_back})...")

        if days_back:
            cutoff_date = datetime.utcnow() - timedelta(days=days_back)
            logger.info(f"[Backfill] Will fetch back to {cutoff_date.strftime('%Y-%m-%d')}")

        total_new = 0
        total_skipped = 0
        pages_fetched = 0
        oldest_timestamp = None
        consecutive_empty_pages = 0

        async with async_session_maker() as session:
            for page in range(max_pages):
                trades = await self.client.get_historical_trades(
                    before_timestamp=oldest_timestamp,
                    limit=500
                )

                if not trades:
                    break

                pages_fetched += 1
                page_new = 0

                for trade_data in trades:
                    if target_market_ids:
                        market_id = trade_data.get("market", "")
                        if market_id not in target_market_ids:
                            continue

                    result = await self.process_single_trade(trade_data, session)
                    if result:
                        page_new += 1
                        total_new += 1
                    else:
                        total_skipped += 1

                if trades:
                    oldest_timestamp = min(t.get("timestamp", 0) for t in trades)
                    oldest_date = datetime.fromtimestamp(oldest_timestamp / 1000)
                    
                    if days_back and oldest_date < cutoff_date:
                        break

                await session.commit()
                await asyncio.sleep(0.3)

                if page_new == 0:
                    consecutive_empty_pages += 1
                else:
                    consecutive_empty_pages = 0

                if stop_on_duplicates and consecutive_empty_pages >= 3:
                    break

        logger.info(f"[Backfill] Complete: {total_new} new trades, {total_skipped} skipped, {pages_fetched} pages")
        return total_new
