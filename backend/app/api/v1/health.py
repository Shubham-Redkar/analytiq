"""AnalytIQ Backend - Health and readiness endpoints."""

import logging

from fastapi import APIRouter, Response

from app.db.session import check_database_connectivity

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/health",
    summary="Liveness check",
    description=(
        "Returns 200 OK when the API process is running. "
        "This endpoint does NOT verify database connectivity."
    ),
    response_description="Service is alive.",
)
async def health_check() -> dict[str, str]:
    """Liveness endpoint - independent of all external dependencies."""
    return {"status": "ok", "service": "analytiq-api"}


@router.get(
    "/ready",
    summary="Readiness check",
    description=(
        "Returns 200 when all required dependencies (currently: PostgreSQL) are reachable. "
        "Returns 503 when any dependency is unavailable."
    ),
    response_description="Service readiness with dependency statuses.",
)
async def readiness_check(response: Response) -> dict[str, object]:
    """Readiness endpoint - verifies PostgreSQL connectivity before accepting traffic."""
    db_ok = await check_database_connectivity()
    db_status = "ok" if db_ok else "unavailable"

    all_ready = db_ok

    if not all_ready:
        response.status_code = 503
        logger.warning("Readiness check failed: database=%s", db_status)

    return {
        "status": "ready" if all_ready else "not_ready",
        "checks": {
            "database": db_status,
        },
    }
