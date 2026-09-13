"""
Enums are the single source of truth (app/domain/enums.py). These tests
guard against the most common way that breaks: a typo'd value, or a second
copy of the same vocabulary drifting from this one.
"""

from app.domain.enums import (
    AttemptResult,
    AuditActor,
    AuditEventType,
    CaseStatus,
    EventSource,
    FailureCategory,
    NormalizedEventType,
    RecoveryActionType,
)


def test_case_status_terminal_statuses():
    terminal = CaseStatus.terminal_statuses()
    assert terminal == {CaseStatus.RECOVERED, CaseStatus.HALTED, CaseStatus.ESCALATED}
    assert CaseStatus.OPEN not in terminal
    assert CaseStatus.WAITING_FOR_RETRY not in terminal


def test_failure_category_matches_prd_categories():
    expected = {"retriable_technical", "card_issue", "insufficient_funds", "customer_action_needed", "unknown"}
    assert {c.value for c in FailureCategory} == expected


def test_recovery_action_type_has_no_duplicate_values():
    values = [a.value for a in RecoveryActionType]
    assert len(values) == len(set(values))


def test_attempt_result_values():
    assert {r.value for r in AttemptResult} == {"pending", "success", "failed", "skipped"}


def test_event_source_distinguishes_simulator_from_real():
    assert EventSource.RAZORPAY_WEBHOOK.value != EventSource.SIMULATOR.value
    assert {s.value for s in EventSource} == {"razorpay_webhook", "simulator"}


def test_audit_actor_covers_agent_system_human_simulator():
    assert {a.value for a in AuditActor} == {"agent", "system", "human", "simulator"}


def test_audit_event_type_no_duplicate_values():
    values = [e.value for e in AuditEventType]
    assert len(values) == len(set(values))


def test_normalized_event_type_covers_all_handled_webhook_events():
    assert NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED.value == "subscription_payment_failed"
    assert NormalizedEventType.SUBSCRIPTION_CHARGED_SUCCESS.value == "subscription_charged_success"
    assert NormalizedEventType.SUBSCRIPTION_PENDING.value == "subscription_pending"
    assert NormalizedEventType.SUBSCRIPTION_HALTED.value == "subscription_halted"
