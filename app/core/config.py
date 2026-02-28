"""
Application configuration.

Loads settings from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from typing import List
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = "postgresql://bud:bud@localhost:5432/buddb"
    
    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://bud.embedlabs.de",
    ]
    
    # OpenProject integration
    PM_URL: str = "https://pm.embedlabs.de"
    PM_TOKEN: str = ""
    
    # File uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100 MB
    
    # Runner settings
    RUNNER_HEARTBEAT_TIMEOUT: int = 120  # seconds
    
    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
