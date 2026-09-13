"""Periodic boundedness and pending-attempt reconciliation sweep."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.domain.decision import Decision, DecisionContext
from app.domain.enums import AttemptResult, AuditActor, AuditEventType, CaseStatus, RecoveryActionType
from app.models.attempt import RecoveryAttempt
from app.models.case import RecoveryCase
from app.services import audit_service, case_service, stopping_rules
from app.services.decision_engine import decide_next_action
from app.services.recovery_executor import _enqueue_execution, schedule_or_execute
from app.workers.celery_app import celery_app


def sweep_stale_cases(db) -> dict[str, int]:
    halted = 0
    requeued = 0
    now = datetime.now(timezone.utc)

    non_terminal = db.query(RecoveryCase).filter(
        ~RecoveryCase.status.in_([status.value for status in CaseStatus.terminal_statuses()])
    ).all()

    for case in non_terminal:
        rule = stopping_rules.get_stopping_rule(db, case.failure_category)
        triggered, reason = stopping_rules.evaluate(case, rule)
        if triggered:
            context = DecisionContext(
                case=case_service.to_snapshot(case),
                failure_category=case.failure_category,
                history=case_service.history_snapshots(case),
                stopping_rule=rule,
                stopping_rule_triggered=True,
                stopping_rule_reason=reason,
            )
            decision = decide_next_action(context)
            schedule_or_execute(db, case, decision)
            audit_service.record_event(
                db,
                case_id=case.id,
                event_type=AuditEventType.STOPPING_RULE_TRIGGERED,
                actor=AuditActor.SYSTEM,
                description=reason or "Periodic sweep triggered stopping rule.",
            )
            halted += 1

    pending = db.query(RecoveryAttempt).filter(RecoveryAttempt.result == AttemptResult.PENDING).all()
    for attempt in pending:
        due = attempt.scheduled_at is None or attempt.scheduled_at.replace(tzinfo=timezone.utc) <= now
        if not due:
            continue
        case = db.query(RecoveryCase).filter(RecoveryCase.id == attempt.case_id).first()
        if case is None or case.status in CaseStatus.terminal_statuses():
            continue
        try:
            _enqueue_execution(attempt.id, eta=None)
            audit_service.record_event(
                db,
                case_id=attempt.case_id,
                event_type=AuditEventType.ACTION_SCHEDULED,
                actor=AuditActor.SYSTEM,
                description=f"Re-enqueued overdue pending attempt {attempt.id}.",
                metadata={"attempt_id": attempt.id, "reconciliation": True},
            )
            requeued += 1
        except Exception as exc:  # broker may still be unavailable
            audit_service.record_event(
                db,
                case_id=attempt.case_id,
                event_type=AuditEventType.ACTION_FAILED,
                actor=AuditActor.SYSTEM,
                description=f"Reconciliation could not enqueue attempt {attempt.id}: {exc}",
                metadata={"attempt_id": attempt.id, "reconciliation": True},
            )

    return {"halted": halted, "requeued": requeued}


@celery_app.task(name="stale_case_check")
def stale_case_check() -> dict[str, int]:
    db = SessionLocal()
    try:
        return sweep_stale_cases(db)
    finally:
        db.close()
