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
from app.core.database import Base, engine
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
