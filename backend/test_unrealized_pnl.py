"""
Test script to verify unrealized P&L implementation.
Run: python backend/test_unrealized_pnl.py
"""
import asyncio
from sqlalchemy import select, func
from app.models.database import async_session_maker, Trade, TraderProfile


async def test_unrealized_pnl():
    """Test that unrealized P&L tracking is working"""
    print("=" * 60)
    print("UNREALIZED P&L IMPLEMENTATION TEST")
    print("=" * 60)

    async with async_session_maker() as session:
        # Test 1: Check for open positions
        print("\n1. Checking for open positions...")
        result = await session.execute(
            select(func.count(Trade.id)).where(Trade.is_win.is_(None))
        )
        open_count = result.scalar() or 0
        print(f"   Total open positions (is_win IS NULL): {open_count}")

        # Test 2: Check if unrealized P&L is populated
        print("\n2. Checking if unrealized P&L is calculated...")
        result = await session.execute(
            select(func.count(Trade.id))
            .where((Trade.is_win.is_(None)) & (Trade.unrealized_pnl_usd.isnot(None)))
        )
        pnl_calculated_count = result.scalar() or 0
        print(f"   Open positions with unrealized_pnl_usd: {pnl_calculated_count}")
        coverage = (pnl_calculated_count / open_count * 100) if open_count > 0 else 0
        print(f"   Coverage: {coverage:.1f}%")

        # Test 3: Sample some trades with unrealized P&L
        if pnl_calculated_count > 0:
            print("\n3. Sample trades with unrealized P&L:")
            result = await session.execute(
                select(Trade)
                .where(Trade.unrealized_pnl_usd.isnot(None))
                .order_by(Trade.unrealized_pnl_usd.desc())
                .limit(5)
            )
            trades = result.scalars().all()
            for i, trade in enumerate(trades, 1):
                print(f"\n   Trade {i}:")
                print(f"      Market: {trade.market_name[:50]}...")
                print(f"      Trade Size: ${trade.trade_size_usd:,.2f}")
                print(f"      Entry Price: {trade.price:.3f}")
                print(f"      Shares: {trade.shares_held:.2f}")
                print(f"      Current Value: ${trade.current_position_value_usd:,.2f}")
                print(f"      Unrealized P&L: ${trade.unrealized_pnl_usd:,.2f}")
                print(f"      Last Updated: {trade.last_pnl_update}")
        else:
            print("\n3. No trades with unrealized P&L calculated yet.")
            print("   Run the backend server to allow the resolution worker to calculate P&L.")

        # Test 4: Check trader profiles
        print("\n4. Checking trader profile unrealized P&L stats...")
        result = await session.execute(
            select(func.count(TraderProfile.id))
            .where(TraderProfile.open_positions_count > 0)
        )
        profiles_with_open = result.scalar() or 0
        print(f"   Trader profiles with open positions: {profiles_with_open}")

        if profiles_with_open > 0:
            print("\n5. Sample trader profiles with open positions:")
            result = await session.execute(
                select(TraderProfile)
                .where(TraderProfile.open_positions_count > 0)
                .order_by(TraderProfile.total_unrealized_pnl.desc())
                .limit(3)
            )
            profiles = result.scalars().all()
            for i, profile in enumerate(profiles, 1):
                print(f"\n   Trader {i}: {profile.wallet_address[:16]}...")
                print(f"      Insider Score: {profile.insider_score:.1f}/100")
                print(f"      Open Positions: {profile.open_positions_count}")
                print(f"      Total Unrealized P&L: ${profile.total_unrealized_pnl:,.2f}")
                print(f"      Avg Unrealized P&L: ${profile.avg_unrealized_pnl:,.2f}")
                print(f"      Unrealized ROI: {profile.unrealized_roi:.1f}%")
                print(f"      Unrealized Win Rate: {profile.unrealized_win_rate:.1f}%")

        # Test 5: Summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        if open_count == 0:
            print("✗ No open positions found in database")
            print("  This is expected if mock mode creates only resolved trades")
        elif pnl_calculated_count == 0:
            print("⚠ Open positions exist but unrealized P&L not calculated yet")
            print("  Start the backend server to run the resolution worker")
        elif pnl_calculated_count < open_count:
            print(f"⚠ Partial coverage: {pnl_calculated_count}/{open_count} positions calculated")
            print("  Some positions may lack price data or be SELL positions (not yet supported)")
        else:
            print("✓ All open positions have unrealized P&L calculated!")

        if profiles_with_open > 0:
            print(f"✓ {profiles_with_open} trader profiles have unrealized P&L metrics")
        else:
            print("⚠ No trader profiles with open positions")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_unrealized_pnl())
