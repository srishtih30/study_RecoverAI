"""Dashboard metrics contract (PRD F7 / Section 9 Success Metrics). Mirror in frontend/src/types/metrics.ts."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class MetricsResponse(BaseModel):
    total_cases: int
    cases_open: int
    cases_recovered: int
    cases_halted: int
    cases_escalated: int

    total_at_risk_amount: int
    total_recovered_amount: int
    recovery_rate: float  # 0.0-1.0

    average_time_to_recovery_seconds: Optional[float] = None

    # TODO(AG): implement false-stop rate + compliance-adherence metrics
    # (PRD Section 9) once stopping_rules + recovery_executor are fully wired.
    false_stop_rate: Optional[float] = None
    compliance_violations: int = 0
