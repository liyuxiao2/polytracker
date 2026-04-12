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
    logger.warning("=" * 70)
    logger.warning("⚠️  WARNING: DATABASE RESET")
    logger.warning("=" * 70)
    logger.info("This will permanently delete:")
    logger.info("  • All trade records")
    logger.info("  • All trader profiles")
    logger.info("  • All market metadata")
    logger.info("  • All tracked markets")
    logger.info("  • All price history")
    logger.info("  • All snapshot data")

    confirm = input("Type 'DELETE ALL DATA' to confirm: ")
    if confirm != "DELETE ALL DATA":
        logger.info("❌ Cancelled.")
        return

    logger.info("[1/2] Dropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    logger.info("[2/2] Creating fresh schema...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("✅ Database reset complete!")
    logger.info("   All tables dropped and recreated with empty schema.")

if __name__ == "__main__":
    asyncio.run(reset_database())
