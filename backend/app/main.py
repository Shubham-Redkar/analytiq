"""AnalytIQ Backend - FastAPI application entry point."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.v1.router import router as v1_router
from app.core.config import configure_logging, get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    Startup: configure logging and validate settings.
    Shutdown: release any held resources.
    """
    settings = get_settings()
    configure_logging(settings)
    logger.info(
        "Starting %s | environment=%s | debug=%s",
        settings.app_name,
        settings.environment,
        settings.debug,
    )
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Application factory - constructs and configures the FastAPI instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "AnalytIQ - Evidence-grounded, multi-agent AI data analytics platform. "
            "API v1 provides liveness, readiness, and future analytical endpoints."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc" if settings.debug else None,
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ------------------------------------------------------------------
    # CORS
    # ------------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # ------------------------------------------------------------------
    # Root & Documentation Endpoints
    # ------------------------------------------------------------------
    @app.get(
        "/",
        summary="API Root",
        description="Returns API service metadata and operational entrypoints.",
        response_description="API service metadata and discovery paths.",
        tags=["root"],
    )
    async def root() -> dict[str, str]:
        """Root endpoint - independent of external dependencies like PostgreSQL."""
        return {
            "name": settings.app_name,
            "description": (
                "AnalytIQ - Evidence-grounded, multi-agent AI data analytics platform API."
            ),
            "version": "0.1.0",
            "docs_url": "/docs",
            "health_url": "/api/v1/health",
            "ready_url": "/api/v1/ready",
            "status": "running",
        }

    @app.get("/api/docs", include_in_schema=False)
    async def api_docs_redirect() -> RedirectResponse:
        """Convenience redirect from legacy /api/docs to canonical /docs."""
        return RedirectResponse(url="/docs")

    # ------------------------------------------------------------------
    # Routers
    # ------------------------------------------------------------------
    app.include_router(v1_router)

    return app


app = create_app()
