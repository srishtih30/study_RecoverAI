"""Simulator API contract (PRD F8: batch test harness). Mirror in frontend/src/types (simulator uses metrics.ts + case.ts types)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.domain.enums import FailureCategory


class SimulationRequest(BaseModel):
    count: int = Field(default=10, ge=1, le=200, description="Number of synthetic failure events to generate.")
    failure_category: Optional[FailureCategory] = Field(
        default=None, description="Restrict simulated failures to one category; omit for a realistic mix."
    )


class SimulationResponse(BaseModel):
    requested: int
    created_case_ids: list[str]
    message: str
