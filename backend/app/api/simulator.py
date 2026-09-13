"""
Batch simulation endpoint (PRD F8).

Generates synthetic failure events (always tagged EventSource.SIMULATOR —
see app/domain/enums.py) and pushes them through the SAME orchestration
pipeline a real Razorpay webhook uses, so the simulator and production path
never drift apart. See app/services/simulator_service.py.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.simulation import SimulationRequest, SimulationResponse
from app.services import simulator_service

router = APIRouter(prefix="/api/simulator", tags=["simulator"])


@router.post("/run", response_model=SimulationResponse)
def run_simulation(payload: SimulationRequest, db: Session = Depends(get_db)) -> SimulationResponse:
    case_ids = simulator_service.run_simulation(db, count=payload.count, failure_category=payload.failure_category)
    return SimulationResponse(
        requested=payload.count,
        created_case_ids=case_ids,
        message=f"Simulated {len(case_ids)} failure event(s). All tagged source=simulator — see EventSource enum.",
    )
