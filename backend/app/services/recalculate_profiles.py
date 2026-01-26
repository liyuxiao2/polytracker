import asyncio
import os
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

# Fix import path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.models.database import Trade, TraderProfile, get_session, engine, async_session_maker
from app.services.insider_detector import InsiderDetector

async def recalculate_profiles():
    print("Starting trader profile recalculation...")
    detector = InsiderDetector()
    
    async with async_session_maker() as session:
        # Get all unique wallet addresses from trades
        result = await session.execute(select(Trade.wallet_address).distinct())
        wallets = result.scalars().all()
        
        print(f"Found {len(wallets)} wallets to process.")
        
        processed = 0
        updated = 0
        
        for wallet in wallets:
            try:
                # Update profile using the detector's logic which now includes relaxed criteria
                profile = await detector.update_trader_profile(wallet, session)
                if profile:
                    updated += 1
                
                processed += 1
                if processed % 100 == 0:
                    print(f"Processed {processed}/{len(wallets)} wallets...")
                    
            except Exception as e:
                print(f"Error processing wallet {wallet}: {e}")
                
        print(f"Recalculation complete. Processed {processed} wallets, updated {updated} profiles.")

if __name__ == "__main__":
    asyncio.run(recalculate_profiles())
