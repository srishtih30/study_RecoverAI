"""
API response contracts for cases.

TODO(AG): frontend/src/types/case.ts must be kept in sync field-for-field
with these schemas. If you change a field name or type here, update the TS
type in the same change — do not silently change this response shape.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.domain.enums import AttemptResult, CaseStatus, EventSource, FailureCategory, RecoveryActionType


class AttemptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: str
    action_type: RecoveryActionType
    result: AttemptResult
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    razorpay_payment_id: Optional[str] = None
    reason: Optional[str] = None
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime


class CaseSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    subscription_id: str
    customer_id: Optional[str] = None
    amount: int
    currency: str
    status: CaseStatus
    failure_category: FailureCategory
    retry_count: int
    opted_out: bool
    source: EventSource
    recovered_amount: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


from app.schemas.decision import DecisionOut


class CaseDetail(CaseSummary):
    failure_reason_raw: Optional[str] = None
    attempts: list[AttemptOut] = []
    last_decision: Optional[DecisionOut] = None
    last_decision_reason: Optional[str] = None
    next_action_at: Optional[datetime] = None


class CaseListResponse(BaseModel):
    items: list[CaseSummary]
    total: int
