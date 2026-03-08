from fastapi import APIRouter
from app.api.v1 import traders, markets, system

api_router = APIRouter()

api_router.include_router(traders.router, tags=["traders"])
api_router.include_router(markets.router, tags=["markets"])
api_router.include_router(system.router, tags=["system"])
