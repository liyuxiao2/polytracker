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
from app.core.database import async_session_maker, Trade, Market, TraderProfile
from sqlalchemy import select, func, distinct
from app.core.config import get_settings

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

            sample_profiles_ok = True
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
                    sample_profiles_ok = False
                else:
                    print(f"    ✅ Wallet {profile.wallet_address[:10]}... only has tracked market trades")

            if sample_profiles_ok:
                print(f"  ✅ PASS: Trader profiles verified")
        else:
            print(f"  ⚠️  No profiles yet (will be created as trades are analyzed)")

        # =====================================================================
        # Check 5: Historical Data Range
        # =====================================================================
        print(f"\n[5/5] Historical Data Range")

        if total_count > 0:
            min_max_result = await session.execute(
                select(func.min(Trade.timestamp), func.max(Trade.timestamp))
            )
            oldest_date, newest_date = min_max_result.one()

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
