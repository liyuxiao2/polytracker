import asyncio
import os
import sys

# Fix import path
sys.path.append(os.path.join(os.path.dirname(__file__), "../.."))

from app.services.polymarket_client import PolymarketClient

async def debug_api():
    client = PolymarketClient()
    print("Fetching recent trades...")
    try:
        trades = await client.get_recent_trades(limit=10)
        for t in trades:
            print(f"Market: {t['market_name']}, Outcome: '{t['outcome']}', Side: {t['side']}")
    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(debug_api())
