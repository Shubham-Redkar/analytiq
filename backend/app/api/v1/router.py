"""AnalytIQ Backend - V1 API router aggregation."""

from fastapi import APIRouter

from app.api.v1 import analysis, auth, datasets, health, sessions, users

router = APIRouter(prefix="/api/v1")

router.include_router(health.router, tags=["health"])
router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(datasets.router, prefix="/datasets", tags=["datasets"])
router.include_router(analysis.router, prefix="/datasets", tags=["analysis"])
router.include_router(analysis.router, prefix="/analysis", tags=["analysis"])
router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
