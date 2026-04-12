from fastapi import APIRouter

from app.domains.markets import router as markets
from app.domains.system import router as system
from app.domains.traders import router as traders

api_router = APIRouter()

api_router.include_router(traders.router, tags=["traders"])
api_router.include_router(markets.router, tags=["markets"])
api_router.include_router(system.router, tags=["system"])
