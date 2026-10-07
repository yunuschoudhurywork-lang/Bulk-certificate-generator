"""
Application configuration using Pydantic Settings.
All environment variables are loaded and validated here.
"""
from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    database_url: str = Field(
        default="postgresql+asyncpg://certgen:password@localhost:5432/certgen",
        description="PostgreSQL database URL with asyncpg driver"
    )
    
    # Redis Configuration
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL"
    )
    
    # Celery Configuration
    celery_broker_url: str = Field(
        default="redis://localhost:6379/0",
        description="Celery message broker URL"
    )
    celery_result_backend: str = Field(
        default="redis://localhost:6379/0",
        description="Celery result backend URL"
    )
    
    # Application Settings
    app_env: str = Field(
        default="development",
        description="Application environment (development, staging, production)"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level"
    )
    
    # Business Logic Settings
    max_recipients_per_job: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum number of recipients allowed per generation job"
    )
    
    # File Storage
    certificate_storage_path: str = Field(
        default="./data/certificates",
        description="Directory path for storing generated certificates"
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    @field_validator("certificate_storage_path")
    @classmethod
    def validate_storage_path(cls, v: str) -> str:
        """Ensure the storage path is valid and create it if it doesn't exist."""
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path.resolve())


# Global settings instance
settings = Settings()
