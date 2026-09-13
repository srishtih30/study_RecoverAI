"""
Case endpoints (PRD F7: dashboard drill-down).

Route -> service mapping:
  list/get case      -> app.services.case_service
  audit history       -> app.services.audit_service
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.domain.enums import CaseStatus
from app.schemas.audit import AuditHistoryResponse, AuditLogOut
from app.schemas.case import CaseDetail, CaseListResponse, CaseSummary
from app.services import audit_service, case_service

router = APIRouter(prefix="/api/cases", tags=["cases"])


@router.get("", response_model=CaseListResponse)
def list_cases(
    status: Optional[CaseStatus] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> CaseListResponse:
    cases, total = case_service.list_cases(db, status=status, limit=limit, offset=offset)
    return CaseListResponse(items=[CaseSummary.model_validate(c) for c in cases], total=total)


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: str, db: Session = Depends(get_db)) -> CaseDetail:
    case = case_service.get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    last_attempt = case.attempts[-1] if case.attempts else None
    decision = case_service.get_case_decision(case)
    detail = CaseDetail.model_validate(case)
    detail.last_decision = decision
    detail.last_decision_reason = decision.reason if decision else (last_attempt.reason if last_attempt else None)
    detail.next_action_at = last_attempt.scheduled_at if last_attempt and last_attempt.result.value == "pending" else None
    return detail


@router.get("/{case_id}/audit", response_model=AuditHistoryResponse)
def get_case_audit(case_id: str, db: Session = Depends(get_db)) -> AuditHistoryResponse:
    case = case_service.get_case(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    entries = audit_service.get_case_audit(db, case_id)
    return AuditHistoryResponse(case_id=case_id, items=[AuditLogOut.model_validate(e) for e in entries])
