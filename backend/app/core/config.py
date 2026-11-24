"""AnalytIQ Backend - Centralized application configuration.

All settings are loaded from environment variables or the .env file.
Pydantic Settings validates values at startup; a misconfigured environment
raises an error before the server accepts requests.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

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
    postgres_host: str = Field(default="127.0.0.1", description="PostgreSQL hostname.")
    postgres_port: int = Field(default=5433, description="PostgreSQL port.")
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
    # Dataset Storage & Limits (M2)
    # ------------------------------------------------------------------
    storage_dir: str = Field(
        default="",
        description="Root storage directory path. If empty, defaults to repository root / storage.",
    )
    max_upload_size_bytes: int = Field(
        default=25 * 1024 * 1024,  # 25 MiB
        description="Maximum upload size in bytes (25 MiB).",
    )
    max_parsed_rows: int = Field(
        default=250_000,
        description="Maximum allowed row count for ingested datasets.",
    )
    max_parsed_columns: int = Field(
        default=200,
        description="Maximum allowed column count for ingested datasets.",
    )
    duckdb_memory_limit: str = Field(
        default="512MB",
        description="Maximum DuckDB memory limit per connection/query.",
    )

    @property
    def storage_path(self) -> Path:
        """Resolve absolute Path to dataset storage root."""
        if self.storage_dir.strip():
            return Path(self.storage_dir).resolve()
        # Default to <repo_root>/storage
        return (Path(__file__).resolve().parents[3] / "storage").resolve()

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"],
        description="Allowed CORS origins (comma-separated string or JSON list).",
    )

    # ------------------------------------------------------------------
    # Authentication & Session
    # ------------------------------------------------------------------
    session_cookie_name: str = Field(
        default="analytiq_session",
        description="Name of the HTTP-only session cookie.",
    )
    session_expire_days: int = Field(
        default=7,
        description="Session validity lifetime in days.",
    )
    cookie_secure: bool = Field(
        default=False,
        description="Enable Secure flag on cookies (HTTPS required).",
    )
    cookie_samesite: str = Field(
        default="lax",
        description="SameSite policy for session cookies (lax, strict, none).",
    )
    max_login_attempts: int = Field(
        default=5,
        description="Maximum consecutive failed login attempts before lockout.",
    )
    lockout_duration_minutes: int = Field(
        default=15,
        description="Duration of account lockout in minutes.",
    )

    # ------------------------------------------------------------------
    # LLM Provider Configuration (M3)
    # ------------------------------------------------------------------
    llm_provider: str = Field(
        default="ollama",
        description="Active LLM provider: 'ollama' or 'mock' (test/dev only).",
    )
    llm_model: str = Field(
        default="qwen2.5:7b",
        description="Model identifier for the active LLM provider.",
    )
    ollama_base_url: str = Field(
        default="http://127.0.0.1:11434",
        description="Server-controlled base URL for local Ollama runtime.",
    )
    llm_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for LLM generation.",
    )
    llm_connect_timeout_seconds: float = Field(
        default=5.0,
        ge=1.0,
        le=60.0,
        description="Connection timeout in seconds for provider HTTP requests.",
    )
    llm_request_timeout_seconds: float = Field(
        default=120.0,
        ge=5.0,
        le=600.0,
        description="Read / request timeout in seconds for provider HTTP requests.",
    )
    llm_max_output_tokens: int = Field(
        default=2048,
        ge=128,
        le=8192,
        description="Maximum generation output tokens.",
    )
    llm_max_provider_retries: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Maximum retries on transient network/provider errors.",
    )

    # ------------------------------------------------------------------
    # Analytical Engine & Query Security (M3)
    # ------------------------------------------------------------------
    analysis_max_question_length: int = Field(
        default=2000,
        ge=10,
        le=10000,
        description="Maximum allowed characters in user analytical question.",
    )
    analysis_max_correction_attempts: int = Field(
        default=1,
        ge=0,
        le=3,
        description="Maximum bounded correction attempts for syntax/schema errors.",
    )
    analysis_max_concurrent_requests: int = Field(
        default=2,
        ge=1,
        le=16,
        description="Maximum concurrent analytical queries executed per application worker.",
    )
    analysis_query_timeout_seconds: float = Field(
        default=15.0,
        ge=1.0,
        le=120.0,
        description="Maximum execution deadline for analytical DuckDB queries.",
    )
    analysis_max_result_rows: int = Field(
        default=1000,
        ge=1,
        le=10000,
        description="Maximum row limit returned to client in analytical result sets.",
    )
    analysis_max_result_bytes: int = Field(
        default=2 * 1024 * 1024,  # 2 MiB
        ge=1024,
        le=50 * 1024 * 1024,
        description="Maximum serialization payload size for analytical results.",
    )
    analysis_duckdb_memory_limit: str = Field(
        default="512MB",
        description="DuckDB in-memory analytical query ceiling.",
    )
    analysis_duckdb_threads: int = Field(
        default=2,
        ge=1,
        le=8,
        description="Maximum CPU threads allocated to DuckDB analytical queries.",
    )

    @field_validator("llm_provider", mode="before")
    @classmethod
    def validate_llm_provider(cls, value: str) -> str:
        provider = str(value).strip().lower()
        if provider not in ("ollama", "mock"):
            raise ValueError(f"Unsupported LLM provider '{value}'. Must be 'ollama' or 'mock'.")
        return provider

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
