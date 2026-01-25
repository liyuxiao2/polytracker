
import asyncio
import os
from app.models.database import async_session_maker, Trade, TraderProfile
from app.services.data_worker import get_worker
from app.services.insider_detector import InsiderDetector
from sqlalchemy import select

async def main():
    print("Initializing...")
    worker = await get_worker()
    
    # 1. Pick a wallet or define one
    # This wallet has activity according to previous test
    target_wallet = "0x088ffbbc6f2c0b3839d2832e75f37e1bcecbc9e7" # from previous step output
    
    print(f"Triggering backfill for {target_wallet}...")
    await worker._backfill_trader_history(target_wallet)
    
    # 2. Check profile stats
    async with async_session_maker() as session:
        result = await session.execute(
            select(TraderProfile).where(TraderProfile.wallet_address == target_wallet)
        )
        profile = result.scalar_one_or_none()
        
        if profile:
            print(f"\nProfile Stats for {target_wallet}:")
            print(f"Total Trades: {profile.total_trades}")
            print(f"Win Rate: {profile.win_rate:.1f}%")
            print(f"ROI: {profile.roi:.1f}%")
            print(f"Profit Factor: {profile.profit_factor:.2f}")
            print(f"Insider Score: {profile.insider_score:.1f}")
        else:
            print("Profile not found!")

if __name__ == "__main__":
    asyncio.run(main())
