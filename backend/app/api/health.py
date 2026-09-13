"""Health check — used by docker/uptime checks and by the frontend to confirm the API is reachable."""

from __future__ import annotations

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    settings = get_settings()
    return {"status": "ok", "environment": settings.environment}
