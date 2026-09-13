"""
FastAPI application factory + route registration.

This is the single place routers get wired into the app. If you add a new
router in app/api/, register it here.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import cases, health, metrics, simulator, webhooks
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="RecoverAI API",
        description="AI Revenue Recovery Agent — subscription payment recovery for Razorpay (test mode).",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(cases.router)
    app.include_router(metrics.router)
    app.include_router(simulator.router)
    app.include_router(webhooks.router)

    return app


app = create_app()
