#!/usr/bin/env python3
"""
Market Discovery Script
=======================
Searches Polymarket API to find the 3 target markets for backtesting.

Usage:
    python discover_markets.py

Output:
    - Prints found markets with metadata
    - Generates .env configuration lines
    - Saves details to discovered_markets.json
"""
import asyncio
from app.domains.ingestion.polymarket_client import PolymarketClient
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Target markets with search keyword variations
TARGET_MARKETS = {
    "Trump 2024 Election": [
        "Trump 2024 election",
        "Trump win 2024",
        "Donald Trump 2024 president",
        "Trump presidential election 2024",
        "2024 presidential election Trump"
    ],
    "Iran Regime Overthrow": [
        "Iran regime overthrow",
        "Iran government change",
        "Iranian regime change",
        "overthrow Iran",
        "Iran regime fall"
    ],
    "Largest Company December 2026": [
        "largest company December 2026",
        "biggest company 2026",
        "market cap 2026",
        "largest company end 2026",
        "most valuable company 2026"
    ]
}

async def discover_markets():
    """Search for and identify the 3 target markets"""
    client = PolymarketClient()
    discovered = {}

    print("=" * 70)
    print("Market Discovery - Searching Polymarket for Target Markets")
    print("=" * 70)

    for market_name, keywords in TARGET_MARKETS.items():
        print(f"\n[Searching] {market_name}")
        print(f"  Keywords: {', '.join(keywords[:3])}...")

        market = await client.find_market_by_keywords(
            keywords,
            allow_closed=True  # Allow closed markets for historical analysis
        )

        if market:
            condition_id = market.get("conditionId")
            question = market.get("question", "")

            # Extract token IDs for YES/NO outcomes
            tokens = market.get("tokens", [])
            yes_token = None
            no_token = None
            for token in tokens:
                if token.get("outcome", "").upper() == "YES":
                    yes_token = token.get("token_id")
                elif token.get("outcome", "").upper() == "NO":
                    no_token = token.get("token_id")

            # Store discovered market
            discovered[market_name] = {
                "condition_id": condition_id,
                "question": question,
                "yes_token_id": yes_token,
                "no_token_id": no_token,
                "closed": market.get("closed", False),
                "liquidity": market.get("liquidityNum", 0),
                "volume": market.get("volumeNum", 0)
            }

            print(f"  ✓ Found: {question[:60]}...")
            print(f"    Condition ID: {condition_id}")
            print(f"    Status: {'Closed/Resolved' if market.get('closed') else 'Active'}")
            print(f"    Liquidity: ${market.get('liquidityNum', 0):,.0f}")
            print(f"    Volume: ${market.get('volumeNum', 0):,.0f}")
        else:
            print(f"  ✗ NOT FOUND")
            print(f"    Try different keywords or manual search on polymarket.com")
            discovered[market_name] = None

    # Summary
    print("\n" + "=" * 70)
    print("Discovery Summary")
    print("=" * 70)

    found_count = sum(1 for v in discovered.values() if v is not None)
    print(f"Found {found_count}/3 markets")

    if found_count == 3:
        # Generate .env configuration
        market_ids = [v["condition_id"] for v in discovered.values() if v]

        print(f"\n📋 Add these lines to backend/.env:")
        print("-" * 70)
        print(f"TRACKED_MARKET_IDS={','.join(market_ids)}")
        print(f"BACKFILL_MAX_PAGES=10000")
        print(f"BACKFILL_STOP_ON_DUPLICATES=false")
        print(f"BACKFILL_RATE_LIMIT_DELAY=0.1")
        print(f"BACKFILL_PARALLEL_MARKETS=true")
        print("-" * 70)

        # Save to JSON for reference
        with open("discovered_markets.json", "w") as f:
            json.dump(discovered, f, indent=2)
        print(f"\n✓ Saved details to discovered_markets.json")

        print(f"\n✅ Next step: Copy the .env lines above, then run setup_3market_system.py")
    else:
        print(f"\n⚠️  WARNING: Not all markets found.")
        print(f"Review keywords in this script or search manually on polymarket.com")

    return discovered

if __name__ == "__main__":
    asyncio.run(discover_markets())
