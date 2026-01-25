"""
Database migration runner for PolyTracker
"""
import asyncio
import asyncpg
import os
from pathlib import Path

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://polytracker:polytracker_dev_password@localhost:5432/polytracker"
)

# Convert asyncpg URL (remove +asyncpg)
DATABASE_URL = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


async def run_migration(migration_file: Path):
    """Run a SQL migration file"""
    print(f"Running migration: {migration_file.name}")

    # Read the SQL file
    with open(migration_file, 'r') as f:
        sql = f.read()

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Execute the migration
        await conn.execute(sql)
        print(f"✓ Migration {migration_file.name} completed successfully")
    except Exception as e:
        print(f"✗ Error running migration {migration_file.name}: {e}")
        raise
    finally:
        await conn.close()


async def main():
    """Run all pending migrations"""
    migrations_dir = Path(__file__).parent / "migrations"

    if not migrations_dir.exists():
        print("No migrations directory found")
        return

    # Get all SQL files in migrations directory, sorted by name
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("No migration files found")
        return

    print(f"Found {len(migration_files)} migration(s)")

    for migration_file in migration_files:
        await run_migration(migration_file)

    print("\nAll migrations completed!")


if __name__ == "__main__":
    asyncio.run(main())
