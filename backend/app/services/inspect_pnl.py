import asyncio
import os
import sys
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

# Fix import path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.models.database import Trade, async_session_maker

async def inspect_trades():
    print("Inspecting resolved trades...")
    
    async with async_session_maker() as session:
        # Get a few wins and losses
        wins_result = await session.execute(
            select(Trade)
            .where(Trade.is_win == True)
            .limit(5)
        )
        wins = wins_result.scalars().all()
        
        losses_result = await session.execute(
            select(Trade)
            .where(Trade.is_win == False)
            .limit(5)
        )
        losses = losses_result.scalars().all()
        
        print("\n--- SAMPLE WINS ---")
        for t in wins:
            print(f"ID: {t.id}, Outcome: {t.outcome}, Resolved: {t.resolved_outcome}, Price: {t.price}, Size: {t.trade_size_usd}, PnL: {t.pnl_usd}")

        print("\n--- SAMPLE LOSSES ---")
        for t in losses:
            print(f"ID: {t.id}, Outcome: {t.outcome}, Resolved: {t.resolved_outcome}, Price: {t.price}, Size: {t.trade_size_usd}, PnL: {t.pnl_usd}")

        # Check for weird data
        # Check if outcome strings match case
        case_mismatch = await session.execute(
            select(Trade)
            .where(
                (Trade.is_resolved == True) &
                (Trade.outcome != None) & 
                (Trade.resolved_outcome != None) &
                (func.upper(Trade.outcome) == func.upper(Trade.resolved_outcome)) &
                (Trade.is_win == False)
            )
            .limit(5)
        )
        mismatches = case_mismatch.scalars().all()
        if mismatches:
            print("\n--- POSSIBLE FALSE LOSSES (Case Mismatch?) ---")
            for t in mismatches:
                print(f"ID: {t.id}, Outcome: {t.outcome}, Resolved: {t.resolved_outcome}, IsWin: {t.is_win}")

if __name__ == "__main__":
    asyncio.run(inspect_trades())
