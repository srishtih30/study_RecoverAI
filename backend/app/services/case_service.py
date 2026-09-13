"""Load/create/update RecoveryCase rows. This is the ONLY module that should query/write `models.RecoveryCase` directly."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session, selectinload

from app.domain.decision import AttemptSnapshot, CaseSnapshot
from app.domain.enums import CaseStatus, FailureCategory
from app.domain.events import NormalizedEvent
from app.models.case import RecoveryCase


def list_cases(
    db: Session, *, status: Optional[CaseStatus] = None, limit: int = 50, offset: int = 0
) -> tuple[list[RecoveryCase], int]:
    query = db.query(RecoveryCase)
    if status is not None:
        query = query.filter(RecoveryCase.status == status)
    total = query.count()
    items = query.order_by(RecoveryCase.created_at.desc()).offset(offset).limit(limit).all()
    return items, total


def get_case(db: Session, case_id: str) -> Optional[RecoveryCase]:
    return (
        db.query(RecoveryCase)
        .options(selectinload(RecoveryCase.attempts))
        .filter(RecoveryCase.id == case_id)
        .first()
    )


def get_open_case_for_subscription(db: Session, subscription_id: str) -> Optional[RecoveryCase]:
    """
    Find an existing non-terminal case for this subscription, if any.

    A new failure on a subscription that already has an open case should
    update that case's history rather than fork a second parallel case for
    the same subscription — see decide-next-action flow in DATA_FLOW.md.
    """
    return (
        db.query(RecoveryCase)
        .filter(RecoveryCase.subscription_id == subscription_id)
        .filter(RecoveryCase.status.notin_(list(CaseStatus.terminal_statuses())))
        .order_by(RecoveryCase.created_at.desc())
        .first()
    )


def get_latest_case_for_subscription(db: Session, subscription_id: str) -> Optional[RecoveryCase]:
    """Find the most recent case for this subscription, regardless of whether it is open or terminal."""
    return (
        db.query(RecoveryCase)
        .filter(RecoveryCase.subscription_id == subscription_id)
        .order_by(RecoveryCase.created_at.desc())
        .first()
    )


def find_open_case_for_event(db: Session, event: NormalizedEvent) -> Optional[RecoveryCase]:
    """
    Find an existing open (non-terminal) case that matches this event.
    Checks subscription_id first, then falls back to matching by payment_id
    across prior recovery attempts.
    """
    if event.subscription_id:
        case = get_open_case_for_subscription(db, event.subscription_id)
        if case is not None:
            return case

    if event.payment_id:
        from app.models.attempt import RecoveryAttempt

        attempt = (
            db.query(RecoveryAttempt)
            .join(RecoveryCase)
            .filter(RecoveryAttempt.razorpay_payment_id == event.payment_id)
            .filter(RecoveryCase.status.notin_(list(CaseStatus.terminal_statuses())))
            .first()
        )
        if attempt is not None:
            return attempt.case

    return None


def mark_case_recovered(
    db: Session,
    case: RecoveryCase,
    *,
    recovered_amount: Optional[int] = None,
    resolved_at: Optional[datetime] = None,
) -> RecoveryCase:
    """
    Transition an open case to RECOVERED.
    Sets status, recovered_amount, resolved_at, and marks any PENDING attempts as SUCCESS.
    """
    from datetime import datetime, timezone
    from app.domain.enums import AttemptResult

    case.status = CaseStatus.RECOVERED
    case.recovered_amount = recovered_amount if (recovered_amount is not None and recovered_amount > 0) else case.amount
    resolution_time = resolved_at or datetime.now(timezone.utc)
    case.resolved_at = resolution_time

    # Close out any PENDING attempts on this case as SUCCESS
    for attempt in case.attempts:
        if attempt.result == AttemptResult.PENDING:
            attempt.result = AttemptResult.SUCCESS
            attempt.executed_at = attempt.executed_at or resolution_time
            db.add(attempt)

    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def get_or_create_case(db: Session, event: NormalizedEvent, failure_category: FailureCategory) -> tuple[RecoveryCase, bool]:
    """Returns (case, created). Does not commit audit entries — callers do that via audit_service."""
    if event.subscription_id:
        existing = get_open_case_for_subscription(db, event.subscription_id)
        if existing is not None:
            existing.failure_category = failure_category
            if event.failure_description:
                existing.failure_reason_raw = event.failure_description
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing, False

    case = RecoveryCase(
        subscription_id=event.subscription_id or f"unknown-{event.provider_event_id}",
        customer_id=event.customer_id,
        amount=event.amount or 0,
        currency=event.currency,
        status=CaseStatus.OPEN,
        failure_category=failure_category,
        failure_reason_raw=event.failure_description,
        source=event.source,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case, True


def apply_decision_to_case(db: Session, case: RecoveryCase, *, next_status: CaseStatus, increment_retry: bool) -> RecoveryCase:
    case.status = next_status
    if increment_retry:
        case.retry_count += 1
    if next_status == CaseStatus.RECOVERED:
        case.recovered_amount = case.amount
    if next_status in CaseStatus.terminal_statuses():
        from datetime import datetime, timezone

        case.resolved_at = datetime.now(timezone.utc)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def to_snapshot(case: RecoveryCase) -> CaseSnapshot:
    """Build the decision engine's read-only view of a case. Keeps the decision engine decoupled from the ORM."""
    last_attempt_at = case.attempts[-1].executed_at if case.attempts else None
    return CaseSnapshot(
        id=case.id,
        status=case.status,
        failure_category=case.failure_category,
        amount=case.amount,
        currency=case.currency,
        retry_count=case.retry_count,
        opted_out=case.opted_out,
        created_at=case.created_at,
        last_attempt_at=last_attempt_at,
    )


def history_snapshots(case: RecoveryCase) -> list[AttemptSnapshot]:
    return [
        AttemptSnapshot(
            action_type=a.action_type,
            result=a.result,
            scheduled_at=a.scheduled_at,
            executed_at=a.executed_at,
        )
        for a in case.attempts
    ]


def get_case_decision(case: RecoveryCase) -> Optional["DecisionOut"]:
    """
    Extracts the latest DecisionOut from the case's most recent recovery attempt, if any.
    Provides the full decision contract (action, next_status, reason, execute_at, metadata)
    for API consumers.
    """
    from app.schemas.decision import DecisionOut

    if not case.attempts:
        return None

    last_attempt = case.attempts[-1]
    return DecisionOut(
        action=last_attempt.action_type,
        next_status=case.status,
        reason=last_attempt.reason or "",
        execute_at=last_attempt.scheduled_at,
        metadata=last_attempt.metadata_json or {},
    )
