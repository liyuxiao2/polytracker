"""
Add unrealized P&L tracking fields to Trade and TraderProfile tables.

This migration adds columns to track unrealized profit/loss on open positions,
providing immediate insider trading signals without waiting for market resolution.

Run: python backend/migrations/add_unrealized_pnl.py
"""
from sqlalchemy import text
import asyncio
import sys
import os

# Add parent directory to path to import app modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.database import engine


async def upgrade():
    """Add unrealized P&L columns to database"""
    print("[Migration] Starting unrealized P&L migration...")

    async with engine.begin() as conn:
        # Trade table additions
        print("[Migration] Adding columns to trades table...")
        try:
            await conn.execute(text(
                "ALTER TABLE trades ADD COLUMN unrealized_pnl_usd FLOAT"
            ))
            print("  - Added unrealized_pnl_usd")
        except Exception as e:
            print(f"  - unrealized_pnl_usd already exists or error: {e}")

        try:
            await conn.execute(text(
                "ALTER TABLE trades ADD COLUMN current_position_value_usd FLOAT"
            ))
            print("  - Added current_position_value_usd")
        except Exception as e:
            print(f"  - current_position_value_usd already exists or error: {e}")

        try:
            await conn.execute(text(
                "ALTER TABLE trades ADD COLUMN shares_held FLOAT"
            ))
            print("  - Added shares_held")
        except Exception as e:
            print(f"  - shares_held already exists or error: {e}")

        try:
            await conn.execute(text(
                "ALTER TABLE trades ADD COLUMN last_pnl_update TIMESTAMP"
            ))
            print("  - Added last_pnl_update")
        except Exception as e:
            print(f"  - last_pnl_update already exists or error: {e}")

        # TraderProfile table additions
        print("[Migration] Adding columns to trader_profiles table...")
        try:
            await conn.execute(text(
                "ALTER TABLE trader_profiles ADD COLUMN open_positions_count INTEGER DEFAULT 0"
            ))
            print("  - Added open_positions_count")
        except Exception as e:
            print(f"  - open_positions_count already exists or error: {e}")

        try:
            await conn.execute(text(
                "ALTER TABLE trader_profiles ADD COLUMN total_unrealized_pnl FLOAT DEFAULT 0.0"
            ))
            print("  - Added total_unrealized_pnl")
        except Exception as e:
            print(f"  - total_unrealized_pnl already exists or error: {e}")

        try:
            await conn.execute(text(
                "ALTER TABLE trader_profiles ADD COLUMN avg_unrealized_pnl FLOAT DEFAULT 0.0"
            ))
            print("  - Added avg_unrealized_pnl")
        except Exception as e:
            print(f"  - avg_unrealized_pnl already exists or error: {e}")

        try:
            await conn.execute(text(
                "ALTER TABLE trader_profiles ADD COLUMN unrealized_roi FLOAT DEFAULT 0.0"
            ))
            print("  - Added unrealized_roi")
        except Exception as e:
            print(f"  - unrealized_roi already exists or error: {e}")

        try:
            await conn.execute(text(
                "ALTER TABLE trader_profiles ADD COLUMN unrealized_win_count INTEGER DEFAULT 0"
            ))
            print("  - Added unrealized_win_count")
        except Exception as e:
            print(f"  - unrealized_win_count already exists or error: {e}")

        try:
            await conn.execute(text(
                "ALTER TABLE trader_profiles ADD COLUMN unrealized_win_rate FLOAT DEFAULT 0.0"
            ))
            print("  - Added unrealized_win_rate")
        except Exception as e:
            print(f"  - unrealized_win_rate already exists or error: {e}")

    print("[Migration] Migration completed successfully!")


async def downgrade():
    """Remove unrealized P&L columns from database"""
    print("[Migration] Removing unrealized P&L columns...")

    async with engine.begin() as conn:
        # Trade table
        print("[Migration] Removing columns from trades table...")
        columns_to_remove = [
            "unrealized_pnl_usd",
            "current_position_value_usd",
            "shares_held",
            "last_pnl_update"
        ]
        for column in columns_to_remove:
            try:
                await conn.execute(text(f"ALTER TABLE trades DROP COLUMN {column}"))
                print(f"  - Removed {column}")
            except Exception as e:
                print(f"  - Error removing {column}: {e}")

        # TraderProfile table
        print("[Migration] Removing columns from trader_profiles table...")
        profile_columns = [
            "open_positions_count",
            "total_unrealized_pnl",
            "avg_unrealized_pnl",
            "unrealized_roi",
            "unrealized_win_count",
            "unrealized_win_rate"
        ]
        for column in profile_columns:
            try:
                await conn.execute(text(f"ALTER TABLE trader_profiles DROP COLUMN {column}"))
                print(f"  - Removed {column}")
            except Exception as e:
                print(f"  - Error removing {column}: {e}")

    print("[Migration] Downgrade completed!")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Unrealized P&L migration")
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Downgrade: remove unrealized P&L columns"
    )
    args = parser.parse_args()

    if args.downgrade:
        asyncio.run(downgrade())
    else:
        asyncio.run(upgrade())
