from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.api.routes import router
from app.models.database import init_db
from app.services.data_worker import get_worker
from app.services.resolution_worker import get_resolution_worker
from app.services.market_watch_worker import get_market_watch_worker
from app.services.snapshot_worker import get_snapshot_worker
import logging
import os

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("[App] Initializing database...")
    await init_db()

    logger.info("[App] Starting background workers...")
    worker = await get_worker()
    worker_task = asyncio.create_task(worker.start())

    resolution_worker = await get_resolution_worker()
    resolution_task = asyncio.create_task(resolution_worker.start())

    market_watch_worker = await get_market_watch_worker()
    market_watch_task = asyncio.create_task(market_watch_worker.start())

    # Start snapshot worker (for backtesting data collection)
    snapshot_worker = None
    snapshot_task = None
    if os.getenv("ENABLE_SNAPSHOT_WORKER", "false").lower() == "true":
        logger.info("[App] Starting snapshot worker for backtesting data...")
        snapshot_worker = await get_snapshot_worker()

        # Auto-discover high-liquidity markets on startup
        min_liquidity = float(os.getenv("AUTO_DISCOVER_MIN_LIQUIDITY", "100000"))
        max_markets = int(os.getenv("AUTO_DISCOVER_MAX_MARKETS", "4"))
        backfill_days = int(os.getenv("BACKFILL_MAX_DAYS", "365"))

        logger.info(f"[App] Auto-discovering up to {max_markets} high-liquidity markets (min ${min_liquidity:,.0f})...")
        discovered = await snapshot_worker.auto_discover_markets(
            min_liquidity=min_liquidity,
            min_volume=100000,
            limit=max_markets
        )

        # Backfill historical data for discovered markets (run in background)
        if discovered:
            logger.info(f"[App] Starting backfill for {len(discovered)} markets ({backfill_days} days)...")
            for market in discovered:
                if market.yes_token_id:
                    asyncio.create_task(snapshot_worker.backfill_price_history(
                        market_id=market.market_id,
                        token_id=market.yes_token_id,
                        outcome="YES",
                        interval="1m",
                        fidelity=1,
                        days_back=backfill_days
                    ))
                if market.no_token_id:
                    asyncio.create_task(snapshot_worker.backfill_price_history(
                        market_id=market.market_id,
                        token_id=market.no_token_id,
                        outcome="NO",
                        interval="1m",
                        fidelity=1,
                        days_back=backfill_days
                    ))

        snapshot_task = asyncio.create_task(snapshot_worker.start())

    yield

    # Shutdown
    logger.info("[App] Shutting down background workers...")
    worker = await get_worker()
    await worker.stop()
    worker_task.cancel()

    resolution_worker = await get_resolution_worker()
    await resolution_worker.stop()
    resolution_task.cancel()

    market_watch_worker = await get_market_watch_worker()
    await market_watch_worker.stop()
    market_watch_task.cancel()

    if os.getenv("ENABLE_SNAPSHOT_WORKER", "false").lower() == "true":
        snapshot_worker = await get_snapshot_worker()
        await snapshot_worker.stop()
        if snapshot_task:
            snapshot_task.cancel()


app = FastAPI(
    title="PolyEdge API",
    description="Real-time insider detection dashboard for Polymarket",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
cors_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:3001,http://127.0.0.1:3000"
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["traders"])


@app.get("/")
async def root():
    return {
        "message": "PolyEdge API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    import os

    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
