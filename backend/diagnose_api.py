import asyncio
import base64
import hmac
import hashlib
import time
from app.config import get_settings
from app.services.polymarket_client import PolymarketClient

async def test_auth():
    settings = get_settings()
    print("--- Diagnostic Report ---")
    print(f"Database URL: {settings.database_url}")
    print(f"Mock Mode: {settings.mock_mode}")
    
    secret = settings.polymarket_api_secret
    if not secret:
        print("API Secret: [MISSING]")
    else:
        print(f"API Secret length: {len(secret)}")
        # Check for non-base64 chars
        clean_secret = "".join(secret.split()).rstrip('=')
        print(f"Cleaned Secret length: {len(clean_secret)}")
        
        try:
            # Test padding
            padding_needed = len(clean_secret) % 4
            padded = clean_secret + ('=' * (4 - padding_needed) if padding_needed else '')
            decoded = base64.b64decode(padded)
            print("Base64 Decode: [SUCCESS]")
        except Exception as e:
            print(f"Base64 Decode: [FAILED] - {e}")

    client = PolymarketClient()
    print("\nTesting Gamma API (Public)...")
    markets = await client.get_active_markets(limit=5)
    if markets:
        print(f"Found {len(markets)} active markets. Gamma API: [OK]")
    else:
        print("Gamma API: [FAILED/EMPTY]")

    print("\nTesting CLOB API (Public)...")
    try:
        url = f"{client.clob_api_base}/sampling-trades" # Public endpoint
        response = await client.client.get(url)
        if response.status_code == 200:
            print("CLOB Public API: [OK]")
        else:
            print(f"CLOB Public API: [FAILED] Status {response.status_code}")
    except Exception as e:
        print(f"CLOB Public API: [ERROR] {e}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(test_auth())
