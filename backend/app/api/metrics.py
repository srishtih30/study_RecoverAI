"""Dashboard aggregate metrics (PRD F7 + Section 9)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.metrics import MetricsResponse
from app.services import metrics_service

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("", response_model=MetricsResponse)
def get_metrics(db: Session = Depends(get_db)) -> MetricsResponse:
    data = metrics_service.compute_metrics(db)
    return MetricsResponse(**data)
