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
import logging
import os
import sys

# Ensure other scripts in the same directory can be imported
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Handle imports gracefully - some may not exist yet
try:
    from discover_markets import discover_markets

    HAS_DISCOVER_MARKETS = True
except ImportError:
    HAS_DISCOVER_MARKETS = False
    print("Warning: discover_markets.py not found - will need to configure markets manually")

try:
    from reset_database import reset_database

    HAS_RESET_DATABASE = True
except ImportError:
    HAS_RESET_DATABASE = False
    print("Warning: reset_database.py not found - will skip database reset")

try:
    from app.domains.ingestion.data_worker import get_worker

    HAS_DATA_WORKER = True
except ImportError:
    try:
        # Fallback to old location
        from app.services.data_worker import get_worker

        HAS_DATA_WORKER = True
    except ImportError:
        HAS_DATA_WORKER = False
        print("Warning: data_worker not found - cannot backfill data")

try:
    from app.core.config import get_settings
except ImportError:
    try:
        # Fallback to old location
        from app.config import get_settings
    except ImportError:
        print("Error: Cannot find config module")
        sys.exit(1)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
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

    if HAS_DISCOVER_MARKETS:
        discovered = await discover_markets()

        found_count = sum(1 for v in discovered.values() if v is not None)
        if found_count != 3:
            print(f"\n❌ ERROR: Expected 3 markets, found {found_count}")
            print("Please review the discover_markets.py script or add markets manually.")
            sys.exit(1)

        # Extract market IDs
        market_ids = [v["condition_id"] for v in discovered.values() if v]
        print("\n✅ Found all 3 markets!")
    else:
        print("⚠️  Market discovery script not available.")
        print("Please enter market IDs manually:")
        market_ids_input = input("Enter comma-separated market IDs: ")
        market_ids = [mid.strip() for mid in market_ids_input.split(",") if mid.strip()]

        if len(market_ids) != 3:
            print(f"\n❌ ERROR: Expected 3 markets, got {len(market_ids)}")
            sys.exit(1)

    # =========================================================================
    # Step 2: Configuration
    # =========================================================================
    print("\n[2/4] Configuration")
    print("-" * 70)
    print("\n📋 Add these lines to backend/.env:")
    print()
    print(f"TRACKED_MARKET_IDS={','.join(market_ids)}")
    print("BACKFILL_MAX_PAGES=10000")
    print("BACKFILL_STOP_ON_DUPLICATES=false")
    print("BACKFILL_RATE_LIMIT_DELAY=0.1")
    print("BACKFILL_PARALLEL_MARKETS=true")
    print()

    confirm = input("Have you updated your .env file? (yes/no): ")
    if confirm.lower() != "yes":
        print("\n⚠️  Please update .env and run this script again.")
        print("   Copy the lines above into backend/.env")
        sys.exit(0)

    # Reload settings to verify that the .env file was updated
    get_settings.cache_clear()
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

    if HAS_RESET_DATABASE:
        print("⚠️  WARNING: This will permanently delete all existing data!")
        print("This includes:")
        print("  • All trade records")
        print("  • All trader profiles")
        print("  • All market data")
        print()

        await reset_database()
    else:
        print("⚠️  Database reset script not available.")
        print("Please manually reset the database if needed.")
        confirm = input("Continue anyway? (yes/no): ")
        if confirm.lower() != "yes":
            sys.exit(0)

    # =========================================================================
    # Step 4: Historical Data Backfill
    # =========================================================================
    print("\n[4/4] Historical Data Backfill")
    print("=" * 70)

    if not HAS_DATA_WORKER:
        print("❌ ERROR: Data worker not available - cannot backfill")
        print("Please check that app.domains.ingestion.data_worker exists")
        sys.exit(1)

    print("Starting parallel backfill for 3 markets...")
    print("This may take 30-90 minutes depending on data volume.")
    print("You can monitor progress in the logs below.")
    print("=" * 70)
    print()

    worker = await get_worker()

    # Check if worker has the parallel backfill method
    if hasattr(worker, "backfill_multiple_markets_parallel"):
        # Run parallel backfill
        total_trades = await worker.backfill_multiple_markets_parallel(market_ids=tracked, max_pages_per_market=10000)
    elif hasattr(worker, "backfill_historical_trades"):
        # Fallback to sequential backfill
        print("⚠️  Parallel backfill not available, running sequentially...")
        total_trades = 0
        for market_id in tracked:
            trades = await worker.backfill_historical_trades(
                max_pages=10000, target_market_ids={market_id}, stop_on_duplicates=False
            )
            total_trades += trades
    else:
        print("❌ ERROR: Worker doesn't have backfill method")
        sys.exit(1)

    # =========================================================================
    # Complete
    # =========================================================================
    print("\n" + "=" * 70)
    print("✅ Setup Complete!")
    print("=" * 70)
    print("\nResults:")
    print(f"  • Total trades ingested: {total_trades:,}")
    print(f"  • Markets tracked: {len(tracked)}")
    print("  • Database: Fresh slate with 3-market data only")
    print()
    print("Next steps:")
    print("  1. Verify setup: python verify_3market_setup.py")
    print("  2. Start server: python run.py")
    print("  3. API docs: http://localhost:8000/docs")
    print("  4. Start frontend: cd ../frontend && npm run dev")
    print()


if __name__ == "__main__":
    asyncio.run(main())
