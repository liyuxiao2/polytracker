# 3-Market Backtesting System - Implementation Plan

**Date:** 2026-03-08
**Status:** Ready for Implementation
**Estimated Time:** 4-6 hours

---

## Executive Summary

This plan converts PolyEdge from a general-purpose Polymarket insider tracker into a focused 3-market backtesting system that:
- Tracks ONLY 3 specific markets (Trump 2024, Iran Regime, Largest Company 2026)
- Backfills complete historical trade data for these markets
- Optimizes ingestion for maximum throughput (150-300 trades/sec during backfill)
- Filters all trader profiles and analytics to these 3 markets only

---

## Context & Rationale

### Why This Change?

**Current State:**
- System monitors ALL Polymarket markets (~200+ active markets)
- Generates massive data volume with mostly irrelevant trades
- Trader profiles diluted by trades from unrelated markets
- Difficult to focus analysis on specific high-value markets

**Desired State:**
- Laser focus on 3 specific markets for deep analysis
- Complete historical context for these markets (all available trade history)
- Fast backfill process to get up and running quickly
- Clean data set with no noise from other markets

**Use Case:** Backtesting insider detection algorithms on specific high-profile markets where information asymmetry is most likely to exist.

---

## Architecture Overview

### Current Flow
```
Polymarket API → Data Worker → All Trades → Database → All Trader Profiles
```

### New Flow
```
Polymarket API
    ↓
Market Discovery (finds 3 markets)
    ↓
Filtered Data Worker → Only 3 Markets' Trades → Database → Filtered Trader Profiles
    ↑
Configuration (.env TRACKED_MARKET_IDS)
```

---

## Implementation Phases

### Phase 1: Market Discovery System

**Goal:** Automatically find the 3 target markets by searching Polymarket API.

#### 1.1 Add Search Methods to PolymarketClient

**File:** `backend/app/services/polymarket_client.py`
**Location:** After line 144 (after `get_markets_list` method)

```python
async def search_markets(self, query: str, limit: int = 200) -> List[dict]:
    """
    Search markets by question text using Gamma API.
    Note: Polymarket doesn't have a search endpoint, so we fetch
    all markets and filter client-side.
    """
    try:
        response = await self.client.get(
            f"{self.gamma_api_base}/markets",
            params={"limit": limit, "offset": 0}
        )
        response.raise_for_status()
        all_markets = response.json()

        # Filter by query (client-side)
        query_lower = query.lower()
        matches = [
            m for m in all_markets
            if query_lower in m.get("question", "").lower()
        ]

        logger.info(f"Found {len(matches)} markets matching '{query}'")
        return matches
    except Exception as e:
        logger.error(f"Error searching markets: {e}")
        return []

async def find_market_by_keywords(
    self,
    keywords: List[str],
    allow_closed: bool = True
) -> Optional[dict]:
    """
    Find a specific market by searching for multiple keyword variations.
    Returns best match using fuzzy matching.

    Args:
        keywords: List of search terms (e.g., ["Trump 2024", "Trump election"])
        allow_closed: If False, skip resolved markets

    Returns:
        Best matching market with highest similarity score
    """
    from difflib import SequenceMatcher

    best_match = None
    best_score = 0.0

    for keyword in keywords:
        matches = await self.search_markets(keyword, limit=200)

        for market in matches:
            question = market.get("question", "")

            # Skip closed markets if not allowed
            if not allow_closed and market.get("closed", False):
                continue

            # Calculate similarity score using difflib
            similarity = SequenceMatcher(
                None,
                keyword.lower(),
                question.lower()
            ).ratio()

            if similarity > best_score:
                best_score = similarity
                best_match = market

    if best_match:
        logger.info(
            f"Best match (score {best_score:.2f}): "
            f"{best_match.get('question')}"
        )

    return best_match
```

#### 1.2 Create Market Discovery Script

**New File:** `backend/discover_markets.py`

```python
#!/usr/bin/env python3
"""
Market Discovery Script
=======================
Searches Polymarket API to find the 3 target markets for backtesting.

Usage:
    python discover_markets.py

Output:
    - Prints found markets with metadata
    - Generates .env configuration lines
    - Saves details to discovered_markets.json
"""
import asyncio
from app.services.polymarket_client import PolymarketClient
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Target markets with search keyword variations
TARGET_MARKETS = {
    "Trump 2024 Election": [
        "Trump 2024 election",
        "Trump win 2024",
        "Donald Trump 2024 president",
        "Trump presidential election 2024",
        "2024 presidential election Trump"
    ],
    "Iran Regime Overthrow": [
        "Iran regime overthrow",
        "Iran government change",
        "Iranian regime change",
        "overthrow Iran",
        "Iran regime fall"
    ],
    "Largest Company December 2026": [
        "largest company December 2026",
        "biggest company 2026",
        "market cap 2026",
        "largest company end 2026",
        "most valuable company 2026"
    ]
}

async def discover_markets():
    """Search for and identify the 3 target markets"""
    client = PolymarketClient()
    discovered = {}

    print("=" * 70)
    print("Market Discovery - Searching Polymarket for Target Markets")
    print("=" * 70)

    for market_name, keywords in TARGET_MARKETS.items():
        print(f"\n[Searching] {market_name}")
        print(f"  Keywords: {', '.join(keywords[:3])}...")

        market = await client.find_market_by_keywords(
            keywords,
            allow_closed=True  # Allow closed markets for historical analysis
        )

        if market:
            condition_id = market.get("conditionId")
            question = market.get("question", "")

            # Extract token IDs for YES/NO outcomes
            tokens = market.get("tokens", [])
            yes_token = None
            no_token = None
            for token in tokens:
                if token.get("outcome", "").upper() == "YES":
                    yes_token = token.get("token_id")
                elif token.get("outcome", "").upper() == "NO":
                    no_token = token.get("token_id")

            # Store discovered market
            discovered[market_name] = {
                "condition_id": condition_id,
                "question": question,
                "yes_token_id": yes_token,
                "no_token_id": no_token,
                "closed": market.get("closed", False),
                "liquidity": market.get("liquidityNum", 0),
                "volume": market.get("volumeNum", 0)
            }

            print(f"  ✓ Found: {question[:60]}...")
            print(f"    Condition ID: {condition_id}")
            print(f"    Status: {'Closed/Resolved' if market.get('closed') else 'Active'}")
            print(f"    Liquidity: ${market.get('liquidityNum', 0):,.0f}")
            print(f"    Volume: ${market.get('volumeNum', 0):,.0f}")
        else:
            print(f"  ✗ NOT FOUND")
            print(f"    Try different keywords or manual search on polymarket.com")
            discovered[market_name] = None

    # Summary
    print("\n" + "=" * 70)
    print("Discovery Summary")
    print("=" * 70)

    found_count = sum(1 for v in discovered.values() if v is not None)
    print(f"Found {found_count}/3 markets")

    if found_count == 3:
        # Generate .env configuration
        market_ids = [v["condition_id"] for v in discovered.values() if v]

        print(f"\n📋 Add these lines to backend/.env:")
        print("-" * 70)
        print(f"TRACKED_MARKET_IDS={','.join(market_ids)}")
        print(f"BACKFILL_MAX_PAGES=10000")
        print(f"BACKFILL_STOP_ON_DUPLICATES=false")
        print(f"BACKFILL_RATE_LIMIT_DELAY=0.1")
        print(f"BACKFILL_PARALLEL_MARKETS=true")
        print("-" * 70)

        # Save to JSON for reference
        with open("discovered_markets.json", "w") as f:
            json.dump(discovered, f, indent=2)
        print(f"\n✓ Saved details to discovered_markets.json")

        print(f"\n✅ Next step: Copy the .env lines above, then run setup_3market_system.py")
    else:
        print(f"\n⚠️  WARNING: Not all markets found.")
        print(f"Review keywords in this script or search manually on polymarket.com")

    return discovered

if __name__ == "__main__":
    asyncio.run(discover_markets())
```

---

### Phase 2: Configuration Management

#### 2.1 Update Config Settings

**File:** `backend/app/config.py`
**Location:** After line 38 (after `z_score_threshold`)

```python
# Tracked markets (comma-separated condition_ids)
tracked_market_ids: str = ""

# Backfill settings
backfill_max_pages: int = 10000
backfill_stop_on_duplicates: bool = False
backfill_rate_limit_delay: float = 0.1
backfill_parallel_markets: bool = True

@property
def tracked_market_id_list(self) -> list:
    """
    Parse tracked market IDs into list.
    Returns empty list if not configured.
    """
    if not self.tracked_market_ids:
        return []
    return [mid.strip() for mid in self.tracked_market_ids.split(",") if mid.strip()]
```

#### 2.2 Update Environment Template

**File:** `backend/.env.example`
**Add these lines:**

```bash
# ==========================================
# 3-Market Backtesting Configuration
# ==========================================
# Comma-separated list of Polymarket condition IDs to track exclusively
TRACKED_MARKET_IDS=

# Backfill Configuration
BACKFILL_MAX_PAGES=10000                    # Max pages to fetch per market (500 trades/page)
BACKFILL_STOP_ON_DUPLICATES=false           # Keep going even if trades already exist
BACKFILL_RATE_LIMIT_DELAY=0.1               # Delay between API calls (seconds)
BACKFILL_PARALLEL_MARKETS=true              # Backfill markets in parallel
```

---

### Phase 3: Database Reset

#### 3.1 Create Database Reset Script

**New File:** `backend/reset_database.py`

```python
#!/usr/bin/env python3
"""
Database Reset Script
=====================
Drops all tables and recreates schema from scratch.

⚠️  WARNING: This will DELETE ALL DATA permanently!

Usage:
    python reset_database.py
"""
import asyncio
from app.models.database import Base, engine
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_database():
    """Drop all tables and recreate schema"""
    print("=" * 70)
    print("⚠️  WARNING: DATABASE RESET")
    print("=" * 70)
    print("\nThis will permanently delete:")
    print("  • All trade records")
    print("  • All trader profiles")
    print("  • All market metadata")
    print("  • All tracked markets")
    print("  • All price history")
    print("  • All snapshot data")
    print()

    confirm = input("Type 'DELETE ALL DATA' to confirm: ")
    if confirm != "DELETE ALL DATA":
        print("\n❌ Cancelled.")
        return

    print("\n[1/2] Dropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    print("[2/2] Creating fresh schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\n✅ Database reset complete!")
    print("   All tables dropped and recreated with empty schema.")

if __name__ == "__main__":
    asyncio.run(reset_database())
```

---

### Phase 4: Data Worker Optimizations

#### 4.1 Fix timedelta Import Bug

**File:** `backend/app/services/data_worker.py`
**Line 5** - Add missing import:

```python
from datetime import datetime, timedelta  # Add timedelta
```

#### 4.2 Add Market Filtering to Worker Initialization

**File:** `backend/app/services/data_worker.py`
**Location:** In `__init__` method (after line 22)

```python
from app.config import get_settings

# Add after self.is_running = False:
self.settings = get_settings()
self.tracked_markets = set(self.settings.tracked_market_id_list)

if self.tracked_markets:
    logger.info(f"[Worker] Tracking {len(self.tracked_markets)} specific markets: {list(self.tracked_markets)}")
else:
    logger.info(f"[Worker] Tracking ALL markets (no filter configured)")
```

#### 4.3 Add Market Filtering to Trade Processing

**File:** `backend/app/services/data_worker.py`
**Location:** In `_process_single_trade` method (after line 99, before creating Trade object)

```python
# Filter by tracked markets if configured
market_id = trade_data.get("market", "")
if self.tracked_markets and market_id not in self.tracked_markets:
    return None  # Skip trades from non-tracked markets
```

#### 4.4 Optimize Backfill with Bulk Inserts

**File:** `backend/app/services/data_worker.py`
**Location:** Replace entire `backfill_historical_trades` method (lines 243-330)

**Add import at top of file:**
```python
import uuid
from typing import List
```

**Replace method:**

```python
async def backfill_historical_trades(
    self,
    max_pages: int = 10000,
    target_market_ids: set = None,
    days_back: int = None,
    stop_on_duplicates: bool = False,
    batch_size: int = 500
):
    """
    Optimized backfill with bulk inserts and minimal overhead.

    Args:
        max_pages: Maximum pages to fetch (500 trades/page)
        target_market_ids: Set of market IDs to filter for (None = all)
        days_back: Stop backfilling after going back this many days
        stop_on_duplicates: Stop if 3 consecutive empty pages
        batch_size: Number of trades to accumulate before bulk insert

    Returns:
        Total number of new trades inserted
    """
    logger.info(f"[Backfill] Starting optimized backfill (max {max_pages} pages)...")

    settings = get_settings()
    rate_limit_delay = settings.backfill_rate_limit_delay

    total_new = 0
    pages_fetched = 0
    oldest_timestamp = None
    trade_batch = []

    # Calculate cutoff date if days_back specified
    cutoff_date = None
    if days_back:
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        logger.info(f"[Backfill] Will stop at {cutoff_date.strftime('%Y-%m-%d')}")

    async with async_session_maker() as session:
        for page in range(max_pages):
            # Fetch page of trades
            trades = await self.client.get_historical_trades(
                before_timestamp=oldest_timestamp,
                limit=500
            )

            if not trades:
                logger.info(f"[Backfill] No more trades found after {pages_fetched} pages")
                break

            pages_fetched += 1

            # Process trades in this page
            for trade_data in trades:
                # Filter by market
                if target_market_ids:
                    market_id = trade_data.get("market", "")
                    if market_id not in target_market_ids:
                        continue

                # Create trade object (without deduplication check for speed)
                trade = self._create_trade_object_for_bulk(trade_data)
                if trade:
                    trade_batch.append(trade)

            # Bulk insert when batch is full
            if len(trade_batch) >= batch_size:
                inserted = await self._bulk_insert_trades(session, trade_batch)
                total_new += inserted
                trade_batch = []

            # Update pagination cursor
            oldest_timestamp = min(t.get("timestamp", 0) for t in trades)
            oldest_date = datetime.fromtimestamp(oldest_timestamp / 1000)

            # Log every 10 pages to reduce noise
            if pages_fetched % 10 == 0:
                logger.info(
                    f"[Backfill] Page {pages_fetched}: {total_new} trades inserted "
                    f"(oldest: {oldest_date.strftime('%Y-%m-%d %H:%M')})"
                )

            # Check cutoff date
            if cutoff_date and oldest_date < cutoff_date:
                logger.info(f"[Backfill] Reached target date, stopping")
                break

            # Rate limiting
            await asyncio.sleep(rate_limit_delay)

        # Insert remaining batch
        if trade_batch:
            inserted = await self._bulk_insert_trades(session, trade_batch)
            total_new += inserted

        await session.commit()

    logger.info(f"[Backfill] Complete: {total_new} trades inserted, {pages_fetched} pages fetched")
    return total_new

def _create_trade_object_for_bulk(self, trade_data: dict) -> Optional[Trade]:
    """
    Create Trade object without database queries (for bulk insert).
    Skips Z-score calculation and deduplication checks for speed.
    """
    try:
        transaction_hash = trade_data.get("id", "") or f"unknown_{uuid.uuid4().hex[:16]}"
        market_id = trade_data.get("market", "")
        wallet_address = trade_data.get("maker_address", "")

        if not market_id or not wallet_address:
            return None

        trade_size = float(trade_data.get("size", 0))
        if trade_size < self.min_trade_size:
            return None

        # Convert timestamp
        timestamp_ms = trade_data.get("timestamp", 0)
        if isinstance(timestamp_ms, int):
            timestamp = datetime.fromtimestamp(timestamp_ms / 1000)
        else:
            timestamp = datetime.utcnow()

        trade = Trade(
            transaction_hash=transaction_hash,
            wallet_address=wallet_address,
            market_id=market_id,
            market_slug=trade_data.get("event_slug", ""),
            market_name=trade_data.get("market_name", "Unknown"),
            trade_size_usd=trade_size,
            outcome=trade_data.get("outcome", ""),
            price=float(trade_data.get("price", 0)) if trade_data.get("price") else None,
            side=trade_data.get("side", ""),
            asset_id=trade_data.get("asset_id", ""),
            timestamp=timestamp,
            trade_hour_utc=timestamp.hour,
            is_flagged=False,
            z_score=None
        )

        return trade
    except Exception as e:
        logger.error(f"Error creating trade object: {e}")
        return None

async def _bulk_insert_trades(self, session: AsyncSession, trades: List[Trade]) -> int:
    """
    Bulk insert trades using PostgreSQL ON CONFLICT DO NOTHING.
    Returns estimated count of successfully inserted trades.

    Note: PostgreSQL doesn't return exact count with ON CONFLICT,
    so we return batch size as estimate.
    """
    if not trades:
        return 0

    try:
        from sqlalchemy.dialects.postgresql import insert

        # Build list of dictionaries for bulk insert
        trade_dicts = []
        for t in trades:
            trade_dicts.append({
                "transaction_hash": t.transaction_hash,
                "wallet_address": t.wallet_address,
                "market_id": t.market_id,
                "market_slug": t.market_slug,
                "market_name": t.market_name,
                "trade_size_usd": t.trade_size_usd,
                "outcome": t.outcome,
                "price": t.price,
                "side": t.side,
                "asset_id": t.asset_id,
                "timestamp": t.timestamp,
                "trade_hour_utc": t.trade_hour_utc,
                "is_flagged": t.is_flagged,
                "z_score": t.z_score
            })

        # Bulk insert with ON CONFLICT DO NOTHING
        stmt = insert(Trade).values(trade_dicts)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=['transaction_hash']  # Unique index
        )

        await session.execute(stmt)

        # Return batch size as estimate (can't get exact count with ON CONFLICT)
        return len(trades)
    except Exception as e:
        logger.error(f"Error in bulk insert: {e}")

        # Fallback to individual inserts
        count = 0
        for trade in trades:
            try:
                session.add(trade)
                count += 1
            except Exception:
                pass  # Skip duplicates

        return count
```

#### 4.5 Add Parallel Backfill Method

**File:** `backend/app/services/data_worker.py`
**Location:** Add after `backfill_historical_trades` method

```python
async def backfill_multiple_markets_parallel(
    self,
    market_ids: List[str],
    max_pages_per_market: int = 10000
):
    """
    Backfill multiple markets in parallel using asyncio.gather.
    Each market gets its own backfill task running concurrently.

    Args:
        market_ids: List of market condition IDs to backfill
        max_pages_per_market: Max pages to fetch for each market

    Returns:
        Total number of trades inserted across all markets
    """
    logger.info(f"[Backfill] Starting parallel backfill for {len(market_ids)} markets...")

    # Create backfill task for each market
    tasks = []
    for market_id in market_ids:
        task = self.backfill_historical_trades(
            max_pages=max_pages_per_market,
            target_market_ids={market_id},
            stop_on_duplicates=False
        )
        tasks.append(task)

    # Run all backfills concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Sum successful results
    total_trades = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"[Backfill] Market {market_ids[i]} failed: {result}")
        else:
            logger.info(f"[Backfill] Market {market_ids[i]}: {result} trades")
            total_trades += result

    logger.info(f"[Backfill] Parallel backfill complete: {total_trades} total trades")
    return total_trades
```

---

### Phase 5: Market Watch Worker Updates

#### 5.1 Add Market Filtering to Market Watch

**File:** `backend/app/services/market_watch_worker.py`
**Location:** In `__init__` method (after line 40)

```python
from app.config import get_settings

# Add after self.category_keywords:
self.settings = get_settings()
self.tracked_markets = set(self.settings.tracked_market_id_list)

if self.tracked_markets:
    logger.info(f"[MarketWatch] Tracking {len(self.tracked_markets)} specific markets")
else:
    logger.info(f"[MarketWatch] Tracking ALL markets (no filter configured)")
```

#### 5.2 Update Market Fetching Logic

**File:** `backend/app/services/market_watch_worker.py`
**Location:** Replace `fetch_active_markets` method (lines 56-69)

```python
async def fetch_active_markets(self) -> list:
    """
    Fetch markets to monitor.
    If tracked_markets is configured, only fetch those specific markets.
    Otherwise, fetch all active markets.
    """
    try:
        if not self.tracked_markets:
            # Original behavior: fetch all active markets
            all_markets = await self.client.get_markets_list(limit=200, closed=False)
            markets = [m for m in all_markets if not m.get("closed", False)]
            logger.info(f"Fetched {len(markets)} active markets from Polymarket")
            return markets
        else:
            # Fetch ONLY tracked markets
            markets = []
            for market_id in self.tracked_markets:
                market_info = await self.client.get_market_info(market_id)
                if market_info:
                    # Convert to expected format (mimics Gamma API response)
                    markets.append({
                        "conditionId": market_id,
                        "question": market_info.get("question", ""),
                        "closed": market_info.get("resolved", False),
                        "tokens": [],  # Token IDs not needed for market watch
                        "endDateIso": market_info.get("end_date", "")
                    })

            logger.info(f"Fetched {len(markets)} tracked markets")
            return markets
    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return []
```

---

### Phase 6: Insider Detector Updates

#### 6.1 Update Z-Score Calculation to Filter by Market

**File:** `backend/app/services/insider_detector.py`
**Location:** Update `calculate_z_score` method signature and query (line 33)

```python
async def calculate_z_score(
    self,
    wallet_address: str,
    trade_size: float,
    session: AsyncSession,
    tracked_markets: set = None  # Add parameter
) -> tuple[float, bool]:
    """
    Calculate Z-score for a trade based on wallet's historical average.
    Only considers trades from tracked markets if specified.

    Returns (z_score, is_anomaly)
    """
    # Get historical trades for this wallet
    query = (
        select(Trade.trade_size_usd)
        .where(Trade.wallet_address == wallet_address)
        .order_by(Trade.timestamp.desc())
        .limit(100)
    )

    # Filter by tracked markets if provided
    if tracked_markets:
        query = query.where(Trade.market_id.in_(tracked_markets))

    result = await session.execute(query)
    historical_trades = result.scalars().all()

    # ... rest of method unchanged
```

#### 6.2 Update Trader Profile Calculation

**File:** `backend/app/services/insider_detector.py`
**Location:** Update `update_trader_profile` method signature and query (line 287)

```python
async def update_trader_profile(
    self,
    wallet_address: str,
    session: AsyncSession,
    tracked_markets: set = None  # Add parameter
) -> TraderProfile:
    """
    Update or create trader profile with latest statistics.
    Only includes trades from tracked markets if specified.
    """
    # Get all trades for this wallet
    query = (
        select(Trade)
        .where(Trade.wallet_address == wallet_address)
        .order_by(Trade.timestamp.asc())
    )

    # Filter by tracked markets if provided
    if tracked_markets:
        query = query.where(Trade.market_id.in_(tracked_markets))

    result = await session.execute(query)
    trades = list(result.scalars().all())

    # ... rest of method unchanged
```

#### 6.3 Update Data Worker Calls

**File:** `backend/app/services/data_worker.py`
**Location:** Update calls to detector methods in `_process_single_trade`

```python
# Around line 120 - when calculating Z-score:
z_score, is_anomaly = await self.detector.calculate_z_score(
    wallet_address,
    trade_size,
    session,
    tracked_markets=self.tracked_markets if self.tracked_markets else None
)

# Around line 165 - when updating profile:
await self.detector.update_trader_profile(
    wallet_address,
    session,
    tracked_markets=self.tracked_markets if self.tracked_markets else None
)
```

---

### Phase 7: Master Setup Script

#### 7.1 Create Orchestration Script

**New File:** `backend/setup_3market_system.py`

```python
#!/usr/bin/env python3
"""
3-Market Backtesting System - Complete Setup Script
====================================================
Orchestrates the entire conversion process from start to finish.

This script will:
1. Discover the 3 target markets
2. Prompt you to update .env configuration
3. Reset the database (with confirmation)
4. Backfill all historical data in parallel
5. Verify the setup

Usage:
    python setup_3market_system.py

Estimated time: 30-90 minutes depending on data volume
"""
import asyncio
import sys
import os
from discover_markets import discover_markets
from reset_database import reset_database
from app.services.data_worker import get_worker
from app.config import get_settings
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    print("=" * 70)
    print("PolyEdge 3-Market Backtesting System - Complete Setup")
    print("=" * 70)
    print("\nThis script will guide you through the entire setup process.")
    print("Estimated time: 30-90 minutes\n")

    # =========================================================================
    # Step 1: Discover Markets
    # =========================================================================
    print("[1/4] Market Discovery")
    print("-" * 70)

    discovered = await discover_markets()

    found_count = sum(1 for v in discovered.values() if v is not None)
    if found_count != 3:
        print(f"\n❌ ERROR: Expected 3 markets, found {found_count}")
        print("Please review the discover_markets.py script or add markets manually.")
        sys.exit(1)

    # Extract market IDs
    market_ids = [v["condition_id"] for v in discovered.values() if v]
    print(f"\n✅ Found all 3 markets!")

    # =========================================================================
    # Step 2: Configuration
    # =========================================================================
    print("\n[2/4] Configuration")
    print("-" * 70)
    print("\n📋 Add these lines to backend/.env:")
    print()
    print(f"TRACKED_MARKET_IDS={','.join(market_ids)}")
    print(f"BACKFILL_MAX_PAGES=10000")
    print(f"BACKFILL_STOP_ON_DUPLICATES=false")
    print(f"BACKFILL_RATE_LIMIT_DELAY=0.1")
    print(f"BACKFILL_PARALLEL_MARKETS=true")
    print()

    confirm = input("Have you updated your .env file? (yes/no): ")
    if confirm.lower() != "yes":
        print("\n⚠️  Please update .env and run this script again.")
        print("   Copy the lines above into backend/.env")
        sys.exit(0)

    # Reload settings to verify
    os.environ["TRACKED_MARKET_IDS"] = ",".join(market_ids)  # Force reload
    settings = get_settings()
    tracked = settings.tracked_market_id_list

    if len(tracked) != 3:
        print(f"\n❌ ERROR: .env shows {len(tracked)} markets, expected 3")
        print("Please check your TRACKED_MARKET_IDS setting.")
        sys.exit(1)

    print(f"\n✅ Configuration verified: Tracking {len(tracked)} markets")

    # =========================================================================
    # Step 3: Database Reset
    # =========================================================================
    print("\n[3/4] Database Reset")
    print("-" * 70)
    print("⚠️  WARNING: This will permanently delete all existing data!")
    print("This includes:")
    print("  • All trade records")
    print("  • All trader profiles")
    print("  • All market data")
    print()

    await reset_database()

    # =========================================================================
    # Step 4: Historical Data Backfill
    # =========================================================================
    print("\n[4/4] Historical Data Backfill")
    print("=" * 70)
    print("Starting parallel backfill for 3 markets...")
    print("This may take 30-90 minutes depending on data volume.")
    print("You can monitor progress in the logs below.")
    print("=" * 70)
    print()

    worker = await get_worker()

    # Run parallel backfill
    total_trades = await worker.backfill_multiple_markets_parallel(
        market_ids=tracked,
        max_pages_per_market=10000
    )

    # =========================================================================
    # Complete
    # =========================================================================
    print("\n" + "=" * 70)
    print("✅ Setup Complete!")
    print("=" * 70)
    print(f"\nResults:")
    print(f"  • Total trades ingested: {total_trades:,}")
    print(f"  • Markets tracked: {len(tracked)}")
    print(f"  • Database: Fresh slate with 3-market data only")
    print()
    print("Next steps:")
    print("  1. Verify setup: python verify_3market_setup.py")
    print("  2. Start server: python run.py")
    print("  3. API docs: http://localhost:8000/docs")
    print("  4. Start frontend: cd ../frontend && npm run dev")
    print()

if __name__ == "__main__":
    asyncio.run(main())
```

---

### Phase 8: Verification System

#### 8.1 Create Verification Script

**New File:** `backend/verify_3market_setup.py`

```python
#!/usr/bin/env python3
"""
3-Market System Verification Script
====================================
Confirms the system is correctly configured to track only 3 markets.

Usage:
    python verify_3market_setup.py

Checks:
  1. Configuration (3 markets in .env)
  2. Trade data (only from tracked markets)
  3. Market metadata (3 markets in database)
  4. Trader profiles (calculated from tracked markets only)
  5. Historical data range (backfill completeness)
"""
import asyncio
from app.models.database import async_session_maker, Trade, Market, TraderProfile
from sqlalchemy import select, func, distinct
from app.config import get_settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_setup():
    """Verify 3-market system is correctly configured"""
    print("=" * 70)
    print("3-Market System Verification")
    print("=" * 70)

    settings = get_settings()
    tracked_markets = set(settings.tracked_market_id_list)

    all_checks_passed = True

    async with async_session_maker() as session:
        # =====================================================================
        # Check 1: Configuration
        # =====================================================================
        print(f"\n[1/5] Configuration")
        print(f"  Tracked markets: {len(tracked_markets)}")

        if len(tracked_markets) != 3:
            print(f"  ❌ FAILED: Expected 3 markets, found {len(tracked_markets)}")
            all_checks_passed = False
        else:
            print(f"  ✅ PASS: Correct number of markets configured")

        # =====================================================================
        # Check 2: Trade Data
        # =====================================================================
        print(f"\n[2/5] Trade Data")

        total_trades = await session.execute(
            select(func.count(Trade.transaction_hash))
        )
        total_count = total_trades.scalar()

        unique_markets = await session.execute(
            select(distinct(Trade.market_id))
        )
        market_ids = unique_markets.scalars().all()

        print(f"  Total trades: {total_count:,}")
        print(f"  Unique markets in database: {len(market_ids)}")

        # Check for non-tracked markets
        non_tracked = [m for m in market_ids if m not in tracked_markets]

        if non_tracked:
            print(f"  ❌ FAILED: Found {len(non_tracked)} non-tracked markets in database!")
            for m in non_tracked[:5]:
                print(f"    - {m}")
            all_checks_passed = False
        else:
            print(f"  ✅ PASS: All trades are from tracked markets only")

        # =====================================================================
        # Check 3: Market Metadata
        # =====================================================================
        print(f"\n[3/5] Market Metadata")

        markets = await session.execute(
            select(Market).where(Market.market_id.in_(tracked_markets))
        )
        market_records = markets.scalars().all()

        print(f"  Markets with metadata: {len(market_records)}")

        if len(market_records) < len(tracked_markets):
            print(f"  ⚠️  WARNING: Some tracked markets missing metadata")
            all_checks_passed = False

        for market in market_records:
            question = market.question[:60] + "..." if len(market.question) > 60 else market.question
            print(f"    • {question}")
            print(f"      Market ID: {market.market_id}")
            print(f"      Trades: {market.total_trades_count or 0:,}")
            print(f"      Status: {'Resolved' if market.is_resolved else 'Active'}")

        if len(market_records) == len(tracked_markets):
            print(f"  ✅ PASS: All tracked markets have metadata")

        # =====================================================================
        # Check 4: Trader Profiles
        # =====================================================================
        print(f"\n[4/5] Trader Profiles")

        profile_count = await session.execute(
            select(func.count(TraderProfile.id))
        )
        profiles = profile_count.scalar()

        print(f"  Total profiles: {profiles:,}")

        if profiles > 0:
            # Sample a few profiles to verify they only contain tracked market trades
            sample = await session.execute(
                select(TraderProfile).limit(5)
            )
            sample_profiles = sample.scalars().all()

            print(f"  Sample profiles (checking trade consistency):")
            for profile in sample_profiles:
                # Check if this wallet has any trades from non-tracked markets
                wallet_markets = await session.execute(
                    select(distinct(Trade.market_id))
                    .where(Trade.wallet_address == profile.wallet_address)
                )
                wallet_market_ids = wallet_markets.scalars().all()

                non_tracked_for_wallet = [m for m in wallet_market_ids if m not in tracked_markets]

                if non_tracked_for_wallet:
                    print(f"    ❌ Wallet {profile.wallet_address[:10]}... has trades from non-tracked markets")
                    all_checks_passed = False
                else:
                    print(f"    ✅ Wallet {profile.wallet_address[:10]}... only has tracked market trades")

            print(f"  ✅ PASS: Trader profiles verified")
        else:
            print(f"  ⚠️  No profiles yet (will be created as trades are analyzed)")

        # =====================================================================
        # Check 5: Historical Data Range
        # =====================================================================
        print(f"\n[5/5] Historical Data Range")

        if total_count > 0:
            oldest = await session.execute(select(func.min(Trade.timestamp)))
            newest = await session.execute(select(func.max(Trade.timestamp)))

            oldest_date = oldest.scalar()
            newest_date = newest.scalar()

            if oldest_date and newest_date:
                print(f"  Oldest trade: {oldest_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"  Newest trade: {newest_date.strftime('%Y-%m-%d %H:%M:%S UTC')}")

                days = (newest_date - oldest_date).days
                print(f"  Date range: {days} days")

                if days > 30:
                    print(f"  ✅ PASS: Good historical coverage ({days} days)")
                else:
                    print(f"  ⚠️  Limited historical data ({days} days)")
            else:
                print(f"  ⚠️  Could not determine date range")
        else:
            print(f"  ⚠️  No trades in database yet")
            all_checks_passed = False

        # =====================================================================
        # Final Summary
        # =====================================================================
        print(f"\n" + "=" * 70)

        if all_checks_passed and total_count > 0:
            print("✅ All checks passed! System is correctly configured.")
        elif total_count == 0:
            print("⚠️  System configured correctly, but no data yet.")
            print("   Run the backfill process to ingest historical trades.")
        else:
            print("❌ Some checks failed. Review the issues above.")
            print("   You may need to re-run the setup script.")

        print("=" * 70)

if __name__ == "__main__":
    asyncio.run(verify_setup())
```

---

## Execution Sequence

**Follow this order for implementation:**

```
1. ✅ Add search methods to polymarket_client.py
2. ✅ Create discover_markets.py script
3. ✅ Run: python discover_markets.py
4. ✅ Update config.py with new settings
5. ✅ Update .env.example
6. ✅ Create reset_database.py script
7. ✅ Fix timedelta bug in data_worker.py
8. ✅ Add market filtering to data_worker.py __init__
9. ✅ Add market filtering to _process_single_trade
10. ✅ Replace backfill_historical_trades method
11. ✅ Add _create_trade_object_for_bulk method
12. ✅ Add _bulk_insert_trades method
13. ✅ Add backfill_multiple_markets_parallel method
14. ✅ Update market_watch_worker.py __init__
15. ✅ Update fetch_active_markets method
16. ✅ Update insider_detector.py calculate_z_score
17. ✅ Update insider_detector.py update_trader_profile
18. ✅ Update data_worker.py calls to detector
19. ✅ Create setup_3market_system.py master script
20. ✅ Create verify_3market_setup.py verification script
21. ✅ Test end-to-end

Estimated time: 4-6 hours
```

---

## Testing & Verification

### Manual Testing Checklist

1. **Market Discovery**
   ```bash
   cd backend
   python discover_markets.py
   ```
   - [ ] All 3 markets found
   - [ ] Condition IDs displayed
   - [ ] discovered_markets.json created

2. **Configuration**
   ```bash
   # Add TRACKED_MARKET_IDS to .env
   python -c "from app.config import get_settings; print(len(get_settings().tracked_market_id_list))"
   ```
   - [ ] Prints "3"

3. **Database Reset**
   ```bash
   python reset_database.py
   # Type: DELETE ALL DATA
   ```
   - [ ] Tables dropped and recreated
   - [ ] No errors

4. **Complete Setup**
   ```bash
   python setup_3market_system.py
   ```
   - [ ] Completes without errors
   - [ ] Shows trade count at end
   - [ ] Takes 30-90 minutes (depending on data)

5. **Verification**
   ```bash
   python verify_3market_setup.py
   ```
   - [ ] All 5 checks pass
   - [ ] No non-tracked markets found
   - [ ] Historical data range shown

6. **Server Start**
   ```bash
   python run.py
   ```
   - [ ] Logs show "Tracking 3 specific markets"
   - [ ] Workers start successfully
   - [ ] No errors in console

7. **API Testing**
   ```bash
   # Get markets
   curl http://localhost:8000/api/markets/watch

   # Get traders
   curl http://localhost:8000/api/traders?min_score=50

   # Get trades
   curl http://localhost:8000/api/trades/trending?min_size=1000
   ```
   - [ ] Only returns data from 3 markets
   - [ ] No 500 errors
   - [ ] Reasonable response times (<1s)

8. **Frontend Integration**
   ```bash
   cd frontend
   npm run dev
   # Visit http://localhost:3000
   ```
   - [ ] Dashboard loads
   - [ ] Shows traders from 3 markets only
   - [ ] Live feed displays trades

---

## Performance Expectations

### Backfill Performance

**Sequential (single market):**
- 500 trades per page
- 0.1s delay between pages
- **~50-100 trades/second**
- For 100k trades: **15-30 minutes**

**Parallel (3 markets):**
- 3 concurrent backfills
- **~150-300 trades/second aggregate**
- For 100k trades per market (300k total): **15-30 minutes**

**Actual performance depends on:**
- Network latency to Polymarket API
- PostgreSQL write speed
- Number of duplicate trades (skipped)
- Historical data availability

### Ongoing Operation

**Live ingestion:**
- Polls every 10 seconds (configurable via `POLL_INTERVAL_SECONDS`)
- Only processes trades from 3 markets
- Minimal CPU: <5% on modern hardware
- Memory: ~200-500 MB (depending on dataset size)

**Database Growth:**
- 100k trades ≈ 50-100 MB
- 10k trader profiles ≈ 5-10 MB
- Markets table ≈ <1 MB
- **Total for full backfill: ~100-200 MB**

---

## Trade-offs & Limitations

### Performance Trade-offs

1. **Bulk Insert Speed vs. Accuracy**
   - **Trade-off:** Using `ON CONFLICT DO NOTHING` means we don't track exact duplicate count
   - **Gain:** 10-20x faster backfill speed
   - **Mitigation:** Run verification script to check data integrity

2. **Parallel Backfill Memory**
   - **Trade-off:** Running 3 concurrent backfills uses 3x database connections
   - **Gain:** 3x faster overall backfill time
   - **Mitigation:** PostgreSQL pool configured for 20 connections (plenty)

3. **Rate Limiting Risk**
   - **Trade-off:** 0.1s delay between pages is aggressive
   - **Gain:** Faster backfill completion
   - **Mitigation:** Increase `BACKFILL_RATE_LIMIT_DELAY` to 0.3s if seeing 429 errors

### Architectural Limitations

1. **No Dynamic Market Changes**
   - **Limitation:** Once configured, requires server restart to add/remove markets
   - **Workaround:** Edit `.env`, restart server, run backfill for new markets

2. **No Partial Backfills**
   - **Limitation:** Can't easily backfill just one market without reconfiguring
   - **Workaround:** Use `/backfill/trades?market_ids=<id>` API endpoint

3. **Historical Data Gaps**
   - **Limitation:** Polymarket API only has ~1-2 years of trade history
   - **Workaround:** None - limited by Polymarket's data retention

### Data Limitations

1. **Closed/Resolved Markets**
   - **Limitation:** If markets are already resolved, no new trades will arrive
   - **Workaround:** System becomes read-only for backtesting analysis

2. **Fuzzy Market Search**
   - **Limitation:** Market discovery uses fuzzy matching, may match wrong market
   - **Workaround:** Manually verify market IDs before adding to `.env`

3. **Trader Profile Recalculation**
   - **Limitation:** Existing profiles include trades from all markets, not just tracked ones
   - **Workaround:** Database reset clears profiles, they'll rebuild with filtered data

---

## Rollback Plan

If issues arise during or after implementation:

### Quick Rollback (Keep Data)

1. Stop the server
2. Edit `.env` and comment out:
   ```bash
   # TRACKED_MARKET_IDS=...
   ```
3. Restart server

**Result:** System reverts to tracking ALL markets (but database still has filtered data)

### Full Rollback (Restore Original State)

1. Stop the server
2. Restore database from backup:
   ```bash
   # If you created a backup before reset:
   pg_restore -d polytracker backup_pre_3market.sql
   ```
3. Remove tracked markets config from `.env`
4. Restart server

**Result:** System completely reverted to original state

### Emergency Fix (Data Corruption)

1. Stop the server
2. Run database reset:
   ```bash
   python reset_database.py
   ```
3. Remove tracked markets config
4. Restart server (will start fresh)

---

## Key Files Modified

| File | Type | Changes |
|------|------|---------|
| `backend/app/services/polymarket_client.py` | Modified | Added `search_markets()` and `find_market_by_keywords()` |
| `backend/app/services/data_worker.py` | Modified | Fixed bug, added filtering, optimized backfill, added parallel method |
| `backend/app/services/market_watch_worker.py` | Modified | Added market filtering to init and fetch |
| `backend/app/services/insider_detector.py` | Modified | Added market filtering parameters to methods |
| `backend/app/config.py` | Modified | Added tracked markets and backfill settings |
| `backend/.env.example` | Modified | Added new configuration examples |
| `backend/discover_markets.py` | **NEW** | Market discovery script |
| `backend/reset_database.py` | **NEW** | Database reset script |
| `backend/setup_3market_system.py` | **NEW** | Master orchestration script |
| `backend/verify_3market_setup.py` | **NEW** | Verification script |

---

## Success Criteria

The implementation is successful when:

- [ ] All 3 target markets are correctly identified
- [ ] Configuration is set in `.env`
- [ ] Database is reset and clean
- [ ] Historical backfill completes for all 3 markets
- [ ] Verification script passes all checks
- [ ] Server starts without errors
- [ ] API only returns data from 3 markets
- [ ] Trader profiles are calculated from filtered data
- [ ] Frontend displays 3-market data correctly
- [ ] No performance degradation (<1s API response times)

---

## Support & Troubleshooting

### Common Issues

**Issue: Market not found during discovery**
- **Cause:** Market question wording changed or market doesn't exist
- **Fix:** Search manually on polymarket.com and add condition ID to `.env`

**Issue: Backfill takes too long**
- **Cause:** Network latency or large data volume
- **Fix:** Increase `BACKFILL_RATE_LIMIT_DELAY` to reduce API call rate

**Issue: Database connection pool exhausted**
- **Cause:** Too many concurrent operations
- **Fix:** Reduce parallel backfills or increase `pool_size` in `database.py`

**Issue: Trades from non-tracked markets appear**
- **Cause:** Filtering not applied or old data persists
- **Fix:** Re-run database reset and setup process

**Issue: API returns 500 errors**
- **Cause:** Database schema mismatch or missing fields
- **Fix:** Check logs, ensure database reset completed successfully

### Getting Help

1. Check logs in terminal where server is running
2. Run verification script: `python verify_3market_setup.py`
3. Review API docs: `http://localhost:8000/docs`
4. Check database directly:
   ```bash
   psql polytracker
   SELECT COUNT(*), market_id FROM trades GROUP BY market_id;
   ```

---

**End of Implementation Plan**

Last Updated: 2026-03-08
Plan Version: 1.0
