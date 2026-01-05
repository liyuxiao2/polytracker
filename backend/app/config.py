from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application configuration settings."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./polyedge.db"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Polymarket API
    polymarket_clob_api: str = "https://clob.polymarket.com"
    polymarket_data_api: str = "https://data-api.polymarket.com"
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
