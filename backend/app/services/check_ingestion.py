import asyncio
import os
import sys
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

# Fix import path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.models.database import Trade, async_session_maker

async def check_ingestion():
    print("Checking ingestion status...")
    
    async with async_session_maker() as session:
        # Count trades
        count = (await session.execute(select(func.count(Trade.id)))).scalar()
        print(f"Total Trades: {count}")
        
        if count == 0:
            print("No trades found yet. Waiting...")
            return

        # Check latest trade
        result = await session.execute(
            select(Trade).order_by(desc(Trade.timestamp)).limit(5)
        )
        trades = result.scalars().all()
        
        print("\n--- LATEST TRADES ---")
        for t in trades:
            print(f"Time: {t.timestamp}, Market: {t.market_name}, Outcome: '{t.outcome}', Side: {t.side}")

if __name__ == "__main__":
    asyncio.run(check_ingestion())
