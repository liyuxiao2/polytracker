"""
Market Watch Worker - Ingests and analyzes markets for suspicious activity and volatility
"""
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from app.models.database import Market, Trade, async_session_maker
from app.services.polymarket_client import PolymarketClient
import logging
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MarketWatchWorker:
    """Worker that ingests markets and calculates metrics for market watch feature"""

    def __init__(self, poll_interval: int = 5):
        """
        Args:
            poll_interval: Seconds between market updates (default 5 minutes)
        """
        self.poll_interval = poll_interval
        self.client = PolymarketClient()
        self.running = False
        self.task = None

        # Category keywords for market classification
        self.category_keywords = {
            "NBA": ["nba", "basketball", "lakers", "warriors", "celtics", "mvp", "finals"],
            "NFL": ["nfl", "football", "super bowl", "quarterback", "patriots", "cowboys"],
            "Politics": ["president", "election", "senate", "congress", "democrat", "republican", "biden", "trump", "harris"],
            "Crypto": ["bitcoin", "ethereum", "crypto", "btc", "eth", "solana", "doge", "blockchain"],
            "Business": ["stock", "tesla", "apple", "amazon", "ipo", "merger", "ceo"],
            "Entertainment": ["oscar", "emmy", "grammy", "movie", "album", "box office"],
            "Science": ["covid", "vaccine", "mars", "spacex", "nasa", "climate"],
            "Sports": ["world cup", "olympics", "soccer", "tennis", "formula 1", "ufc"],
        }

    def categorize_market(self, question: str) -> str:
        """Categorize a market based on its question text"""
        if not question:
            return "Other"

        question_lower = question.lower()

        for category, keywords in self.category_keywords.items():
            for keyword in keywords:
                if keyword in question_lower:
                    return category

        return "Other"

    async def fetch_active_markets(self) -> list:
        """Fetch active markets from Polymarket API"""
        try:
            # Fetch markets from CLOB API
            all_markets = await self.client.get_markets_list(limit=200, closed=False)

            # Filter out closed markets (API returns both closed and active despite parameter)
            markets = [m for m in all_markets if not m.get("closed", False)]

            logger.info(f"Fetched {len(markets)} active markets from Polymarket (filtered from {len(all_markets)} total)")
            return markets
        except Exception as e:
            logger.error(f"Error fetching markets: {e}")
            return []

    async def update_market_from_api(self, session: AsyncSession, market_data: dict):
        """Update or create a market from API data"""
        try:
            market_id = market_data.get("condition_id") or market_data.get("id")
            if not market_id:
                return

            # Check if market exists
            result = await session.execute(
                select(Market).where(Market.market_id == market_id)
            )
            market = result.scalar_one_or_none()

            question = market_data.get("question", "")
            category = self.categorize_market(question)

            if not market:
                # Create new market
                market = Market(
                    market_id=market_id,
                    condition_id=market_data.get("condition_id"),
                    question=question,
                    category=category,
                    is_resolved=market_data.get("closed", False),
                    end_date=self._parse_datetime(market_data.get("end_date_iso")),
                    last_checked=datetime.utcnow()
                )
                session.add(market)
            else:
                # Update existing market
                market.question = question
                market.category = category
                market.is_resolved = market_data.get("closed", False)
                market.end_date = self._parse_datetime(market_data.get("end_date_iso"))
                market.last_checked = datetime.utcnow()

            # Update prices from tokens
            tokens = market_data.get("tokens", [])
            for token in tokens:
                outcome = token.get("outcome")
                price = token.get("price")
                if outcome == "Yes" and price is not None:
                    market.current_yes_price = float(price)
                elif outcome == "No" and price is not None:
                    market.current_no_price = float(price)

            return market

        except Exception as e:
            logger.error(f"Error updating market {market_data.get('id')}: {e}")
            return None

    async def calculate_market_metrics(self, session: AsyncSession, market: Market):
        """Calculate metrics for a market based on its trades"""
        try:
            # Get all trades for this market
            result = await session.execute(
                select(Trade).where(Trade.market_id == market.market_id)
            )
            trades = result.scalars().all()

            if not trades:
                return

            # Basic counts
            market.total_trades_count = len(trades)
            market.suspicious_trades_count = sum(1 for t in trades if t.is_flagged)

            # Volume and traders
            market.total_volume = sum(t.trade_size_usd for t in trades)
            market.unique_traders_count = len(set(t.wallet_address for t in trades))

            # Calculate volatility (price movements in last 24h)
            recent_trades = [
                t for t in trades
                if t.timestamp and t.timestamp >= datetime.utcnow() - timedelta(hours=24)
            ]

            if recent_trades and len(recent_trades) > 1:
                prices = [t.price for t in recent_trades if t.price is not None]
                if len(prices) > 1:
                    market.volatility_score = statistics.stdev(prices) * 100  # As percentage

                    # Price change in 24h
                    sorted_trades = sorted(recent_trades, key=lambda x: x.timestamp)
                    if sorted_trades[0].price and sorted_trades[-1].price:
                        old_price = sorted_trades[0].price
                        new_price = sorted_trades[-1].price
                        if old_price > 0:
                            market.price_change_24h = ((new_price - old_price) / old_price) * 100

            # Calculate suspicion score (0-100)
            suspicion_factors = []

            # Factor 1: Percentage of flagged trades (0-40 points)
            if market.total_trades_count > 0:
                flagged_pct = (market.suspicious_trades_count / market.total_trades_count) * 100
                suspicion_factors.append(min(flagged_pct * 0.8, 40))  # Cap at 40 points

            # Factor 2: High volume concentration (0-20 points)
            if market.unique_traders_count > 0 and market.total_volume > 0:
                avg_volume_per_trader = market.total_volume / market.unique_traders_count
                if avg_volume_per_trader > 5000:  # High concentration
                    suspicion_factors.append(20)
                elif avg_volume_per_trader > 2000:
                    suspicion_factors.append(10)

            # Factor 3: Recent activity spike (0-20 points)
            if len(recent_trades) > 10:
                recent_flagged = sum(1 for t in recent_trades if t.is_flagged)
                if recent_flagged > 5:
                    suspicion_factors.append(20)
                elif recent_flagged > 2:
                    suspicion_factors.append(10)

            # Factor 4: Timing (trades close to resolution) (0-20 points)
            if market.is_resolved and market.resolution_time:
                late_trades = [
                    t for t in trades
                    if t.hours_before_resolution is not None and 0 < t.hours_before_resolution < 24
                ]
                if len(late_trades) > 5:
                    suspicion_factors.append(20)
                elif len(late_trades) > 2:
                    suspicion_factors.append(10)

            market.suspicion_score = min(sum(suspicion_factors), 100)
            market.metrics_updated_at = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error calculating metrics for market {market.market_id}: {e}")

    def _parse_datetime(self, date_str: str) -> datetime:
        """Parse ISO datetime string"""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            return None

    async def run_once(self):
        """Run a single market update cycle"""
        logger.info("Starting market watch update cycle...")

        async with async_session_maker() as session:
            # Fetch markets from API
            markets_data = await self.fetch_active_markets()

            # Update markets in database
            for market_data in markets_data:
                market = await self.update_market_from_api(session, market_data)
                if market:
                    await self.calculate_market_metrics(session, market)

            await session.commit()

            logger.info(f"Updated {len(markets_data)} markets")

    async def start(self):
        """Start the market watch worker"""
        if self.running:
            logger.warning("Market watch worker is already running")
            return

        self.running = True
        logger.info("Market Watch Worker started")

        while self.running:
            try:
                await self.run_once()
            except Exception as e:
                logger.error(f"Error in market watch cycle: {e}")

            if self.running:
                # Wait before next cycle
                logger.info(f"Waiting {self.poll_interval} seconds until next market update...")
                await asyncio.sleep(self.poll_interval)

    async def stop(self):
        """Stop the market watch worker"""
        logger.info("Stopping market watch worker...")
        self.running = False

    async def run(self):
        """Run the market watch worker continuously"""
        await self.start()


_market_watch_worker_instance = None


async def get_market_watch_worker() -> MarketWatchWorker:
    """Get or create the singleton market watch worker instance"""
    global _market_watch_worker_instance
    if _market_watch_worker_instance is None:
        _market_watch_worker_instance = MarketWatchWorker(poll_interval=300)
    return _market_watch_worker_instance


async def main():
    """Main entry point"""
    worker = MarketWatchWorker(poll_interval=300)  # 5 minutes
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
