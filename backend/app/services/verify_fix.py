import asyncio
import os
import sys
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Fix import path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.models.database import Trade, TraderProfile, async_session_maker

async def verify_fix():
    print("Verifying fix...")
    
    async with async_session_maker() as session:
        # Check whales count
        whales_result = await session.execute(
            select(func.count(TraderProfile.id))
            .where(TraderProfile.insider_score > 0)
        )
        whales_count = whales_result.scalar() or 0
        print(f"Traders with insider score > 0: {whales_count}")
        
        # Check Total PnL from Trades
        trade_pnl_result = await session.execute(
            select(func.sum(Trade.pnl_usd))
        )
        total_trade_pnl = trade_pnl_result.scalar() or 0
        print(f"Sum of Trade.pnl_usd: {total_trade_pnl:,.2f}")
        
        # Check Total PnL from Profiles (should match roughly)
        profile_pnl_result = await session.execute(
            select(func.sum(TraderProfile.total_pnl))
        )
        total_profile_pnl = profile_pnl_result.scalar() or 0
        print(f"Sum of TraderProfile.total_pnl: {total_profile_pnl:,.2f}")
        
        diff = abs(total_trade_pnl - total_profile_pnl)
        if diff < 1000: # Allow small float diff
            print("SUCCESS: PnL is synchronized!")
        else:
            print(f"WARNING: PnL mismatch of {diff:,.2f}")

if __name__ == "__main__":
    asyncio.run(verify_fix())
