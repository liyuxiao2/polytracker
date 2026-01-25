
import asyncio
import os
from sqlalchemy import text
from app.models.database import engine

async def main():
    print("Connecting to database to add missing columns...")
    async with engine.begin() as conn:
        try:
            print("Adding 'roi' column to trader_profiles...")
            await conn.execute(text("ALTER TABLE trader_profiles ADD COLUMN IF NOT EXISTS roi FLOAT DEFAULT 0.0"))
            print("✓ Added 'roi'")
        except Exception as e:
            print(f"Warning adding roi: {e}")

        try:
            print("Adding 'profit_factor' column to trader_profiles...")
            await conn.execute(text("ALTER TABLE trader_profiles ADD COLUMN IF NOT EXISTS profit_factor FLOAT DEFAULT 0.0"))
            print("✓ Added 'profit_factor'")
        except Exception as e:
            print(f"Warning adding profit_factor: {e}")
            
    print("Done. Please restart the backend server if errors persist.")

if __name__ == "__main__":
    asyncio.run(main())
