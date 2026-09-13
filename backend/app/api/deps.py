"""Shared FastAPI dependencies. Routers import from here rather than reaching into app.db directly."""

from __future__ import annotations

from app.db.session import get_db

__all__ = ["get_db"]
