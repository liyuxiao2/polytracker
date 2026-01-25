#!/usr/bin/env python3
"""
Migration script to transfer data from SQLite to PostgreSQL.

Usage:
    python migrate_to_postgres.py

Requirements:
    - SQLite database file exists at ./polyedge.db
    - PostgreSQL is running (via docker-compose up postgres)
    - Dependencies installed: pip install -r requirements.txt
"""

import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, text
from app.models.database import Base, Trade, TraderProfile, Market

# Database URLs
SQLITE_URL = "sqlite+aiosqlite:///./polyedge.db"
POSTGRES_URL = "postgresql+asyncpg://polytracker:polytracker_dev_password@localhost:5432/polytracker"


async def migrate_data():
    """Migrate all data from SQLite to PostgreSQL."""

    print("=" * 60)
    print("PostgreSQL Migration Script")
    print("=" * 60)

    # Create engines
    print("\n1. Connecting to databases...")
    sqlite_engine = create_async_engine(SQLITE_URL, echo=False)
    postgres_engine = create_async_engine(POSTGRES_URL, echo=False)

    sqlite_session_maker = async_sessionmaker(sqlite_engine, class_=AsyncSession, expire_on_commit=False)
    postgres_session_maker = async_sessionmaker(postgres_engine, class_=AsyncSession, expire_on_commit=False)

    try:
        # Test connections
        async with sqlite_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("   ✓ Connected to SQLite")

        async with postgres_engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        print("   ✓ Connected to PostgreSQL")

        # Create tables in PostgreSQL
        print("\n2. Creating tables in PostgreSQL...")
        async with postgres_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)  # Drop existing tables
            await conn.run_sync(Base.metadata.create_all)
        print("   ✓ Tables created")

        # Migrate Markets
        print("\n3. Migrating Markets...")
        async with sqlite_session_maker() as sqlite_session:
            result = await sqlite_session.execute(select(Market))
            markets = result.scalars().all()

            if markets:
                async with postgres_session_maker() as postgres_session:
                    for market in markets:
                        # Create new instance to avoid session conflicts
                        new_market = Market(
                            market_id=market.market_id,
                            condition_id=market.condition_id,
                            question=market.question,
                            is_resolved=market.is_resolved,
                            resolved_outcome=market.resolved_outcome,
                            resolution_time=market.resolution_time,
                            end_date=market.end_date,
                            last_checked=market.last_checked,
                        )
                        postgres_session.add(new_market)

                    await postgres_session.commit()
                print(f"   ✓ Migrated {len(markets)} markets")
            else:
                print("   ℹ No markets to migrate")

        # Migrate Trades
        print("\n4. Migrating Trades...")
        async with sqlite_session_maker() as sqlite_session:
            result = await sqlite_session.execute(select(Trade))
            trades = result.scalars().all()

            if trades:
                async with postgres_session_maker() as postgres_session:
                    batch_size = 1000
                    for i in range(0, len(trades), batch_size):
                        batch = trades[i:i + batch_size]

                        for trade in batch:
                            new_trade = Trade(
                                wallet_address=trade.wallet_address,
                                market_id=trade.market_id,
                                market_slug=getattr(trade, 'market_slug', None),
                                market_name=trade.market_name,
                                trade_size_usd=trade.trade_size_usd,
                                outcome=trade.outcome,
                                price=trade.price,
                                timestamp=trade.timestamp,
                                is_flagged=trade.is_flagged,
                                flag_reason=trade.flag_reason,
                                z_score=trade.z_score,
                                side=trade.side,
                                trade_type=trade.trade_type,
                                transaction_hash=trade.transaction_hash,
                                asset_id=trade.asset_id,
                                is_resolved=trade.is_resolved,
                                resolved_outcome=trade.resolved_outcome,
                                is_win=trade.is_win,
                                pnl_usd=trade.pnl_usd,
                                hours_before_resolution=trade.hours_before_resolution,
                                trade_hour_utc=trade.trade_hour_utc,
                            )
                            postgres_session.add(new_trade)

                        await postgres_session.commit()
                        print(f"   ✓ Migrated batch {i // batch_size + 1} ({min(i + batch_size, len(trades))}/{len(trades)} trades)")

                print(f"   ✓ Migrated {len(trades)} trades total")
            else:
                print("   ℹ No trades to migrate")

        # Migrate Trader Profiles
        print("\n5. Migrating Trader Profiles...")
        async with sqlite_session_maker() as sqlite_session:
            result = await sqlite_session.execute(select(TraderProfile))
            profiles = result.scalars().all()

            if profiles:
                async with postgres_session_maker() as postgres_session:
                    for profile in profiles:
                        new_profile = TraderProfile(
                            wallet_address=profile.wallet_address,
                            total_trades=profile.total_trades,
                            resolved_trades=profile.resolved_trades,
                            winning_trades=profile.winning_trades,
                            win_rate=profile.win_rate,
                            avg_bet_size=profile.avg_bet_size,
                            std_bet_size=profile.std_bet_size,
                            max_bet_size=profile.max_bet_size,
                            total_volume=profile.total_volume,
                            total_pnl=profile.total_pnl,
                            insider_score=profile.insider_score,
                            last_updated=profile.last_updated,
                            flagged_trades_count=profile.flagged_trades_count,
                            flagged_wins_count=profile.flagged_wins_count,
                            total_yes_bets=profile.total_yes_bets,
                            total_no_bets=profile.total_no_bets,
                            outcome_bias=profile.outcome_bias,
                            total_buys=profile.total_buys,
                            total_sells=profile.total_sells,
                            first_seen=profile.first_seen,
                            wallet_age_days=profile.wallet_age_days,
                            unique_markets_count=profile.unique_markets_count,
                            market_concentration=profile.market_concentration,
                            avg_hours_before_resolution=profile.avg_hours_before_resolution,
                            off_hours_trade_pct=profile.off_hours_trade_pct,
                            days_since_last_trade=profile.days_since_last_trade,
                            avg_entry_price=profile.avg_entry_price,
                            longshot_win_rate=profile.longshot_win_rate,
                            large_bet_win_rate=profile.large_bet_win_rate,
                        )
                        postgres_session.add(new_profile)

                    await postgres_session.commit()
                print(f"   ✓ Migrated {len(profiles)} trader profiles")
            else:
                print("   ℹ No trader profiles to migrate")

        # Verify migration
        print("\n6. Verifying migration...")
        async with postgres_session_maker() as postgres_session:
            markets_count = await postgres_session.execute(select(Market))
            trades_count = await postgres_session.execute(select(Trade))
            profiles_count = await postgres_session.execute(select(TraderProfile))

            print(f"   ✓ PostgreSQL now contains:")
            print(f"     - {len(markets_count.scalars().all())} markets")
            print(f"     - {len(trades_count.scalars().all())} trades")
            print(f"     - {len(profiles_count.scalars().all())} trader profiles")

        print("\n" + "=" * 60)
        print("✓ Migration completed successfully!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Update your .env file with the PostgreSQL DATABASE_URL")
        print("2. Restart your application")
        print("3. Optional: Backup your SQLite database and remove it")
        print("")

    except Exception as e:
        print(f"\n✗ Error during migration: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        await sqlite_engine.dispose()
        await postgres_engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate_data())
