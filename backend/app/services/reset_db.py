import asyncio
import os
import sys
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Fix import path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.models.database import engine

async def reset_db():
    print("WARNING: This will delete ALL trades and trader profiles.")
    
    async with engine.begin() as conn:
        print("Truncating tables...")
        # Use DELETE instead of TRUNCATE for SQLite compatibility if needed, though we use Postgres
        # Cascading delete might be safer
        await conn.execute(text("TRUNCATE TABLE trades RESTART IDENTITY CASCADE;"))
        await conn.execute(text("TRUNCATE TABLE trader_profiles RESTART IDENTITY CASCADE;"))
        # Also clean markets if we want a full refresh, but maybe keep them
        # await conn.execute(text("TRUNCATE TABLE markets RESTART IDENTITY CASCADE;"))
        
        print("Database cleared!")

if __name__ == "__main__":
    asyncio.run(reset_db())
