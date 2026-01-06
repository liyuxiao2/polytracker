from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio

from app.api.routes import router
from app.models.database import init_db
from app.services.data_worker import get_worker
from app.services.resolution_checker import get_resolution_checker
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events for the FastAPI application."""
    # Startup
    print("[App] Initializing database...")
    await init_db()

    print("[App] Starting background worker...")
    worker = await get_worker()
    worker_task = asyncio.create_task(worker.start())

    print("[App] Starting resolution checker...")
    resolution_checker = await get_resolution_checker()
    resolution_task = asyncio.create_task(resolution_checker.start())

    yield

    # Shutdown
    print("[App] Shutting down services...")
    worker = await get_worker()
    await worker.stop()
    worker_task.cancel()

    resolution_checker = await get_resolution_checker()
    await resolution_checker.stop()
    resolution_task.cancel()


settings = get_settings()

app = FastAPI(
    title="PolyEdge API",
    description="Real-time insider detection dashboard for Polymarket",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
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

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level="info"
    )
