"""
Recovery executor — turns a Decision into a RecoveryAttempt and, when the
action requires it, a Celery job that eventually calls Razorpay.

This is the ONLY service module that may reach into
`app.integrations.razorpay` for a real provider call. The decision engine
never does this directly (see decision_engine.py docstring).

Two entry points:
  * `schedule_or_execute(...)` — called synchronously from
    webhook_orchestrator right after a Decision is made. Creates the
    RecoveryAttempt row and, for actions with a side effect, enqueues
    `app.workers.tasks.execute_action` (immediately for RETRY_NOW, at
    `decision.execute_at` for delayed actions). Imports the Celery task
    lazily to avoid a service-layer -> worker-layer import cycle at module
    load time.
  * `execute_attempt(...)` — called BY that Celery task (not from the web
    request path). Does the actual Razorpay call and updates the attempt +
    case + audit trail.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.domain.decision import Decision
from app.domain.enums import AttemptResult, AuditActor, AuditEventType, CaseStatus, RecoveryActionType
from app.models.attempt import RecoveryAttempt
from app.models.case import RecoveryCase
from app.services import audit_service, case_service

# Actions that require calling out to Razorpay / a notification channel.
ACTIONS_REQUIRING_EXECUTION = {
    RecoveryActionType.RETRY_NOW,
    RecoveryActionType.RETRY_LATER,
    RecoveryActionType.SEND_PAYMENT_UPDATE_LINK,
    RecoveryActionType.NOTIFY_CUSTOMER,
}


def schedule_or_execute(db: Session, case: RecoveryCase, decision: Decision) -> RecoveryAttempt:
    attempt = RecoveryAttempt(
        case_id=case.id,
        action_type=decision.action,
        result=AttemptResult.PENDING if decision.action in ACTIONS_REQUIRING_EXECUTION else AttemptResult.SKIPPED,
        scheduled_at=decision.execute_at,
        reason=decision.reason,
        metadata_json=decision.metadata,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    increment_retry = decision.action in (RecoveryActionType.RETRY_NOW, RecoveryActionType.RETRY_LATER)
    case_service.apply_decision_to_case(db, case, next_status=decision.next_status, increment_retry=increment_retry)

    if decision.action in ACTIONS_REQUIRING_EXECUTION:
        audit_service.record_event(
            db,
            case_id=case.id,
            event_type=AuditEventType.ACTION_SCHEDULED,
            actor=AuditActor.AGENT,
            description=f"Scheduled {decision.action.value} — {decision.reason}",
            metadata={"attempt_id": attempt.id, "execute_at": decision.execute_at.isoformat() if decision.execute_at else None},
        )
        try:
            _enqueue_execution(attempt.id, eta=decision.execute_at)
        except Exception as exc:  # noqa: BLE001 — broker (Redis) may legitimately be unreachable
            # Degrade gracefully: the case/attempt/audit trail above is
            # already committed, so we don't lose state. The attempt stays
            # PENDING and simply won't run until something re-enqueues it.
            # The periodic stale-case sweep reconciles overdue PENDING
            # attempts and re-enqueues them when the broker is available.
            audit_service.record_event(
                db,
                case_id=case.id,
                event_type=AuditEventType.ACTION_FAILED,
                actor=AuditActor.SYSTEM,
                description=f"Could not enqueue {decision.action.value} for execution (broker unreachable?): {exc}",
                metadata={"attempt_id": attempt.id},
            )
    else:
        audit_service.record_event(
            db,
            case_id=case.id,
            event_type=AuditEventType.DECISION_MADE,
            actor=AuditActor.AGENT,
            description=f"Decision: {decision.action.value} — {decision.reason}",
            metadata={"attempt_id": attempt.id},
        )

    return attempt


def _enqueue_execution(attempt_id: str, *, eta: datetime | None) -> None:
    # Lazy import: keeps `app.services` importable without Celery/Redis
    # configured (e.g. in tests that never touch async execution).
    from app.workers.tasks.execute_action import execute_action

    if eta is not None:
        execute_action.apply_async(args=[attempt_id], eta=eta)
    else:
        execute_action.delay(attempt_id)


def execute_attempt(db: Session, attempt_id: str) -> RecoveryAttempt:
    """
    Called from the Celery task. Performs the actual Razorpay call (via the
    integration layer — never the SDK directly) and updates state.

    An attempt is SUCCESS when its recovery action was successfully handed
    to the provider. Revenue is only marked recovered after a matching
    subscription.charged webhook arrives.
    """
    from app.integrations.razorpay.client import get_razorpay_client

    attempt = db.query(RecoveryAttempt).filter(RecoveryAttempt.id == attempt_id).first()
    if attempt is None:
        raise ValueError(f"RecoveryAttempt {attempt_id} not found")

    case = db.query(RecoveryCase).filter(RecoveryCase.id == attempt.case_id).first()
    if case is None:
        raise ValueError(f"RecoveryCase {attempt.case_id} not found for attempt {attempt_id}")

    client = get_razorpay_client()

    try:
        result: dict = {}
        if attempt.action_type in (RecoveryActionType.RETRY_NOW, RecoveryActionType.RETRY_LATER):
            result = client.retry_subscription_charge(case.subscription_id)
            attempt.razorpay_payment_id = result.get("payment_id")
        elif attempt.action_type == RecoveryActionType.SEND_PAYMENT_UPDATE_LINK:
            result = client.create_payment_update_link(
                case.subscription_id,
                case.customer_id,
                amount=case.amount,
                currency=case.currency,
            )
        elif attempt.action_type == RecoveryActionType.NOTIFY_CUSTOMER:
            result = client.notify_customer(case.customer_id, reason=attempt.reason or "")

        attempt.metadata_json = {**(attempt.metadata_json or {}), "provider_result": result}
        attempt.result = AttemptResult.SUCCESS
        attempt.executed_at = datetime.now(timezone.utc)
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        audit_service.record_event(
            db,
            case_id=case.id,
            event_type=AuditEventType.ACTION_EXECUTED,
            actor=AuditActor.AGENT,
            description=f"Executed {attempt.action_type.value} successfully.",
            metadata={"attempt_id": attempt.id, "razorpay_payment_id": attempt.razorpay_payment_id},
        )

        # Executing a recovery action is not the same as recovering revenue.
        # A retry remains open until Razorpay sends subscription.charged; a
        # payment link remains open until its resulting payment is observed.
        if attempt.action_type in (RecoveryActionType.RETRY_NOW, RecoveryActionType.RETRY_LATER):
            case_service.apply_decision_to_case(
                db, case, next_status=CaseStatus.WAITING_FOR_RETRY, increment_retry=False
            )

    except Exception as exc:  # noqa: BLE001 — deliberately broad: any provider failure must still be audited
        attempt.result = AttemptResult.FAILED
        attempt.executed_at = datetime.now(timezone.utc)
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        audit_service.record_event(
            db,
            case_id=case.id,
            event_type=AuditEventType.ACTION_FAILED,
            actor=AuditActor.AGENT,
            description=f"Execution of {attempt.action_type.value} failed: {exc}",
            metadata={"attempt_id": attempt.id},
        )

    return attempt
