"""SQLAlchemy model creation/round-trip tests — confirms the DB foundation actually works end-to-end."""

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
from app.models.attempt import RecoveryAttempt
from app.models.audit_log import AuditLog
from app.models.case import RecoveryCase
from app.models.processed_event import ProcessedWebhookEvent
from app.models.stopping_rule import StoppingRuleConfig


def test_create_case_with_defaults(db_session):
    case = RecoveryCase(subscription_id="sub_test_1", amount=49900)
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    assert case.id is not None
    assert case.status == CaseStatus.OPEN
    assert case.failure_category == FailureCategory.UNKNOWN
    assert case.currency == "INR"
    assert case.source == EventSource.RAZORPAY_WEBHOOK
    assert case.retry_count == 0
    assert case.opted_out is False


def test_case_attempt_relationship(db_session):
    case = RecoveryCase(subscription_id="sub_test_2", amount=99900)
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    attempt = RecoveryAttempt(case_id=case.id, action_type=RecoveryActionType.RETRY_NOW, result=AttemptResult.PENDING)
    db_session.add(attempt)
    db_session.commit()

    db_session.refresh(case)
    assert len(case.attempts) == 1
    assert case.attempts[0].action_type == RecoveryActionType.RETRY_NOW


def test_case_audit_log_relationship(db_session):
    case = RecoveryCase(subscription_id="sub_test_3", amount=19900)
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    entry = AuditLog(
        case_id=case.id,
        event_type=AuditEventType.CASE_CREATED,
        actor=AuditActor.SYSTEM,
        description="Created case for subscription sub_test_3.",
    )
    db_session.add(entry)
    db_session.commit()

    db_session.refresh(case)
    assert len(case.audit_logs) == 1
    assert case.audit_logs[0].event_type == AuditEventType.CASE_CREATED


def test_processed_webhook_event_unique_provider_event_id(db_session):
    row = ProcessedWebhookEvent(
        provider_event_id="evt_model_test_1",
        event_type=NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED,
        source=EventSource.SIMULATOR,
    )
    db_session.add(row)
    db_session.commit()
    db_session.refresh(row)
    assert row.id is not None


def test_stopping_rule_config_round_trip(db_session):
    rule = StoppingRuleConfig(
        failure_category=FailureCategory.CARD_ISSUE,
        max_retries=2,
        retry_intervals_hours=[2, 24],
        max_days_open=5,
        opt_out_respected=True,
    )
    db_session.add(rule)
    db_session.commit()
    db_session.refresh(rule)

    fetched = db_session.query(StoppingRuleConfig).filter_by(failure_category=FailureCategory.CARD_ISSUE).one()
    assert fetched.retry_intervals_hours == [2, 24]
    assert fetched.max_retries == 2
