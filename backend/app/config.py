from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application configuration settings."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./polyedge.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Polymarket APIs
    polymarket_clob_api: str = "https://clob.polymarket.com"
    polymarket_gamma_api: str = "https://gamma-api.polymarket.com"
    polymarket_data_api: str = "https://data-api.polymarket.com"

    # Polymarket API Authentication (for authenticated endpoints)
    # To get these credentials:
    # 1. Use py-clob-client: client.create_or_derive_api_creds()
    # 2. Or generate from your Polygon wallet private key
    polymarket_api_key: Optional[str] = None
    polymarket_api_secret: Optional[str] = None
    polymarket_api_passphrase: Optional[str] = None

    # Mock mode - set to False to use real APIs
    mock_mode: bool = True

    # Worker settings
    poll_interval_seconds: int = 30
    min_trade_size_usd: float = 5000.0

    # Detection thresholds
    z_score_threshold: float = 3.0

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
