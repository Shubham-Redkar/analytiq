"""AnalytIQ Backend - Centralized application configuration.

All settings are loaded from environment variables or the .env file.
Pydantic Settings validates values at startup; a misconfigured environment
raises an error before the server accepts requests.
"""

import json
import logging
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_name: str = Field(default="AnalytIQ API", description="Human-readable service name.")
    environment: str = Field(default="development", description="Runtime environment.")
    debug: bool = Field(default=False, description="Enable debug mode.")

    # ------------------------------------------------------------------
    # Server
    # ------------------------------------------------------------------
    api_host: str = Field(default="0.0.0.0", description="Bind host for the API server.")
    api_port: int = Field(default=8000, description="Bind port for the API server.")

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    postgres_host: str = Field(default="localhost", description="PostgreSQL hostname.")
    postgres_port: int = Field(default=5432, description="PostgreSQL port.")
    postgres_db: str = Field(default="analytiq_db", description="PostgreSQL database name.")
    postgres_user: str = Field(default="analytiq", description="PostgreSQL username.")
    postgres_password: str = Field(default="", description="PostgreSQL password.")

    @property
    def database_url(self) -> str:
        """Async SQLAlchemy database URL assembled from individual fields."""
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins (comma-separated string or JSON list).",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> list[str]:
        """Accept a JSON list string, a comma-separated string, or a list of origins."""
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                return json.loads(stripped)
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(v) for v in value]
        return []

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field(default="INFO", description="Logging level.")

    @field_validator("log_level", mode="before")
    @classmethod
    def uppercase_log_level(cls, value: str) -> str:
        return value.upper()

    @field_validator("environment", mode="before")
    @classmethod
    def lowercase_environment(cls, value: str) -> str:
        return value.lower()


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings.

    Using lru_cache ensures settings are parsed once at startup and reused
    across the application, avoiding repeated environment lookups.
    """
    return Settings()


def configure_logging(settings: Settings) -> None:
    """Configure root logger based on application settings."""
    numeric_level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
