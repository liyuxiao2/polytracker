
import asyncio
import os
from sqlalchemy import select
from app.models.database import get_session, TraderProfile
from app.services.polymarket_client import PolymarketClient

# Set env to use postgres if needed, or rely on .env
# The user migrated to postgres, so DATABASE_URL should be in .env or consistent with dev.sh

async def main():
    # 1. Get a wallet address
    async for session in get_session():
        result = await session.execute(select(TraderProfile.wallet_address).limit(1))
        wallet = result.scalar_one_or_none()
        if not wallet:
            print("No wallets found in DB.")
            return
        
        print(f"Testing with wallet: {wallet}")
        
        # 2. Fetch activity
        client = PolymarketClient()
        try:
            activity = await client.get_user_activity(wallet, limit=5)
            print("Activity Response:")
            import json
            print(json.dumps(activity, indent=2))
        finally:
            await client.close()
        break

if __name__ == "__main__":
    asyncio.run(main())
