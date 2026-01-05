from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import asyncio
from app.api.routes import router
from app.models.database import init_db
from app.services.data_worker import get_worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events for the FastAPI application.
    """
    # Startup
    print("[App] Initializing database...")
    await init_db()

    print("[App] Starting background worker...")
    worker = await get_worker()
    worker_task = asyncio.create_task(worker.start())

    yield

    # Shutdown
    print("[App] Shutting down background worker...")
    worker = await get_worker()
    await worker.stop()
    worker_task.cancel()


app = FastAPI(
    title="PolyEdge API",
    description="Real-time insider detection dashboard for Polymarket",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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
