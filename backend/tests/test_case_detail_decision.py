"""Tests for Case Detail API exposing the full DecisionOut contract."""

from datetime import datetime, timezone

from app.domain.enums import CaseStatus, EventSource, NormalizedEventType
from app.domain.events import NormalizedEvent
from app.models.case import RecoveryCase
from app.services import webhook_orchestrator


def _failed_event(sub_id: str, provider_event_id: str, failure_code: str = "card_declined") -> NormalizedEvent:
    return NormalizedEvent(
        provider_event_id=provider_event_id,
        event_type=NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED,
        source=EventSource.SIMULATOR,
        subscription_id=sub_id,
        customer_id="cust_test_decision",
        amount=99900,
        currency="INR",
        failure_code=failure_code,
        failure_description=f"Failure due to {failure_code}",
        occurred_at=datetime.now(timezone.utc),
    )


def test_get_case_detail_returns_full_decision(client, db_session):
    sub_id = "sub_case_detail_test_1"
    res = webhook_orchestrator.process_event(
        db_session, _failed_event(sub_id, "evt_detail_1", failure_code="expired_card")
    )
    case_id = res["case_id"]

    resp = client.get(f"/api/cases/{case_id}")
    assert resp.status_code == 200
    data = resp.json()

    # Full DecisionOut verification
    assert "last_decision" in data
    assert data["last_decision"] is not None

    decision = data["last_decision"]
    assert decision["action"] == "send_payment_update_link"
    assert decision["next_status"] == "waiting_for_customer"
    assert "Card issue detected" in decision["reason"]
    assert isinstance(decision["metadata"], dict)

    # Backward compatibility checks
    assert data["last_decision_reason"] == decision["reason"]


def test_get_case_detail_with_delayed_retry_decision(client, db_session):
    sub_id = "sub_case_detail_test_retry"
    res = webhook_orchestrator.process_event(
        db_session, _failed_event(sub_id, "evt_detail_retry", failure_code="gateway_error")
    )
    case_id = res["case_id"]

    resp = client.get(f"/api/cases/{case_id}")
    assert resp.status_code == 200
    data = resp.json()

    decision = data["last_decision"]
    assert decision is not None
    assert decision["action"] == "retry_later"
    assert decision["next_status"] == "waiting_for_retry"
    assert decision["execute_at"] is not None
    assert data["next_action_at"] == decision["execute_at"]


def test_get_case_detail_without_attempts_returns_null_decision(client, db_session):
    case = RecoveryCase(
        subscription_id="sub_no_attempts",
        customer_id="cust_raw",
        amount=10000,
        currency="INR",
        status=CaseStatus.OPEN,
        source=EventSource.SIMULATOR,
    )
    db_session.add(case)
    db_session.commit()
    db_session.refresh(case)

    resp = client.get(f"/api/cases/{case.id}")
    assert resp.status_code == 200
    data = resp.json()

    assert data["last_decision"] is None
    assert data["last_decision_reason"] is None
    assert data["next_action_at"] is None
