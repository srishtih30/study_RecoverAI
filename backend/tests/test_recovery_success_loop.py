"""Tests for the recovery success loop: subscription.charged -> case RECOVERED."""

from datetime import datetime, timezone
import hashlib
import hmac
import json

from app.domain.enums import AttemptResult, AuditEventType, CaseStatus, EventSource, NormalizedEventType
from app.domain.events import NormalizedEvent
from app.models.case import RecoveryCase
from app.services import case_service, metrics_service, webhook_orchestrator


def _failed_event(sub_id: str, provider_event_id: str, amount: int = 150000) -> NormalizedEvent:
    return NormalizedEvent(
        provider_event_id=provider_event_id,
        event_type=NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED,
        source=EventSource.SIMULATOR,
        subscription_id=sub_id,
        customer_id="cust_test_1",
        amount=amount,
        currency="INR",
        failure_code="insufficient_funds",
        failure_description="Not enough balance in account",
        occurred_at=datetime.now(timezone.utc),
    )


def _charged_event(
    sub_id: str, provider_event_id: str, amount: int = 150000, payment_id: str | None = None
) -> NormalizedEvent:
    return NormalizedEvent(
        provider_event_id=provider_event_id,
        event_type=NormalizedEventType.SUBSCRIPTION_CHARGED_SUCCESS,
        source=EventSource.SIMULATOR,
        subscription_id=sub_id,
        customer_id="cust_test_1",
        payment_id=payment_id or "pay_success_123",
        amount=amount,
        currency="INR",
        occurred_at=datetime.now(timezone.utc),
    )


def test_subscription_charged_marks_open_case_recovered(db_session):
    sub_id = "sub_recov_test_1"
    # Step 1: Failure creates case
    fail_res = webhook_orchestrator.process_event(db_session, _failed_event(sub_id, "evt_fail_1", amount=250000))
    case_id = fail_res["case_id"]
    assert case_id is not None

    case = case_service.get_case(db_session, case_id)
    assert case is not None
    assert case.status != CaseStatus.RECOVERED
    assert case.recovered_amount is None
    assert case.resolved_at is None

    # Step 2: Successful charge arrives for same subscription
    success_res = webhook_orchestrator.process_event(
        db_session, _charged_event(sub_id, "evt_success_1", amount=250000, payment_id="pay_recov_1")
    )
    assert success_res["status"] == "ok"
    assert success_res["duplicate"] is False
    assert success_res["case_id"] == case_id

    # Step 3: Verify case status, recovered amount, resolved_at
    db_session.refresh(case)
    assert case.status == CaseStatus.RECOVERED
    assert case.recovered_amount == 250000
    assert case.resolved_at is not None

    # Step 4: Verify audit trail
    audit_events = [log.event_type for log in case.audit_logs]
    assert AuditEventType.CASE_RECOVERED in audit_events

    # Step 5: Verify metrics
    metrics = metrics_service.compute_metrics(db_session)
    assert metrics["cases_recovered"] >= 1
    assert metrics["total_recovered_amount"] >= 250000


def test_subscription_charged_closes_pending_attempts(db_session):
    sub_id = "sub_recov_test_attempts"
    fail_res = webhook_orchestrator.process_event(db_session, _failed_event(sub_id, "evt_fail_attempts"))
    case_id = fail_res["case_id"]
    case = case_service.get_case(db_session, case_id)

    # Any attempts that were scheduled as PENDING should be closed as SUCCESS on recovery
    webhook_orchestrator.process_event(db_session, _charged_event(sub_id, "evt_success_attempts"))
    db_session.refresh(case)
    for attempt in case.attempts:
        assert attempt.result != AttemptResult.PENDING


def test_duplicate_success_webhook_is_idempotent(db_session):
    sub_id = "sub_recov_test_dup"
    fail_res = webhook_orchestrator.process_event(db_session, _failed_event(sub_id, "evt_fail_dup"))
    case_id = fail_res["case_id"]

    # First delivery
    res_1 = webhook_orchestrator.process_event(db_session, _charged_event(sub_id, "evt_success_dup", amount=100000))
    assert res_1["duplicate"] is False
    assert res_1["case_id"] == case_id

    case = case_service.get_case(db_session, case_id)
    initial_audit_count = len(case.audit_logs)

    # Duplicate delivery of the exact same provider event ID
    res_2 = webhook_orchestrator.process_event(db_session, _charged_event(sub_id, "evt_success_dup", amount=100000))
    assert res_2["duplicate"] is True
    assert res_2["case_id"] == case_id

    db_session.refresh(case)
    assert case.recovered_amount == 100000
    # Audit trail on the case does not add a second CASE_RECOVERED
    recovered_events = [l for l in case.audit_logs if l.event_type == AuditEventType.CASE_RECOVERED]
    assert len(recovered_events) == 1


def test_already_terminal_case_remains_safe(db_session):
    sub_id = "sub_recov_terminal"
    fail_res = webhook_orchestrator.process_event(db_session, _failed_event(sub_id, "evt_fail_term"))
    case_id = fail_res["case_id"]
    case = case_service.get_case(db_session, case_id)

    # Manually halt the case (terminal status)
    case.status = CaseStatus.HALTED
    case.resolved_at = datetime.now(timezone.utc)
    db_session.add(case)
    db_session.commit()

    # Success event arrives with a new event ID
    res = webhook_orchestrator.process_event(db_session, _charged_event(sub_id, "evt_success_term_new", amount=50000))
    assert res["status"] == "ok"
    assert res["duplicate"] is False
    assert res["case_id"] == case_id

    # The case remains HALTED, not mutated to RECOVERED, no double counting
    db_session.refresh(case)
    assert case.status == CaseStatus.HALTED
    assert case.recovered_amount is None


def test_success_event_without_open_case_does_not_create_case(db_session):
    sub_id = "sub_never_failed_before"
    count_before = db_session.query(RecoveryCase).count()

    res = webhook_orchestrator.process_event(db_session, _charged_event(sub_id, "evt_success_orphan"))
    assert res["status"] == "ok"
    assert res["duplicate"] is False
    assert res["case_id"] is None

    count_after = db_session.query(RecoveryCase).count()
    assert count_after == count_before


def test_end_to_end_raw_webhook_signature_success(client):
    secret = "test_webhook_secret"
    sub_id = "sub_e2e_webhook_test"

    # Step 1: Deliver raw payment.failed webhook
    fail_payload = {
        "entity": "event",
        "event": "payment.failed",
        "created_at": 1735689600,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_fail_e2e",
                    "amount": 199900,
                    "currency": "INR",
                    "error_code": "card_declined",
                    "error_description": "Card was declined",
                    "customer_id": "cust_e2e",
                }
            },
            "subscription": {"entity": {"id": sub_id}},
        },
    }
    fail_body = json.dumps(fail_payload).encode("utf-8")
    fail_sig = hmac.new(secret.encode("utf-8"), fail_body, hashlib.sha256).hexdigest()

    resp_fail = client.post(
        "/api/webhooks/razorpay",
        content=fail_body,
        headers={"X-Razorpay-Signature": fail_sig, "X-Razorpay-Event-Id": "evt_e2e_fail_1"},
    )
    assert resp_fail.status_code == 200
    fail_json = resp_fail.json()
    case_id = fail_json["case_id"]
    assert case_id is not None

    # Verify case is open via API
    case_resp = client.get(f"/api/cases/{case_id}")
    assert case_resp.status_code == 200
    assert case_resp.json()["status"] != "recovered"

    # Step 2: Deliver raw subscription.charged webhook
    success_payload = {
        "entity": "event",
        "event": "subscription.charged",
        "created_at": 1735693200,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_success_e2e",
                    "amount": 199900,
                    "currency": "INR",
                    "customer_id": "cust_e2e",
                }
            },
            "subscription": {
                "entity": {
                    "id": sub_id,
                    "charge_amount": 199900,
                }
            },
        },
    }
    success_body = json.dumps(success_payload).encode("utf-8")
    success_sig = hmac.new(secret.encode("utf-8"), success_body, hashlib.sha256).hexdigest()

    resp_success = client.post(
        "/api/webhooks/razorpay",
        content=success_body,
        headers={"X-Razorpay-Signature": success_sig, "X-Razorpay-Event-Id": "evt_e2e_success_1"},
    )
    assert resp_success.status_code == 200
    success_json = resp_success.json()
    assert success_json["duplicate"] is False
    assert success_json["case_id"] == case_id

    # Step 3: Verify case is now recovered
    case_resp_after = client.get(f"/api/cases/{case_id}")
    assert case_resp_after.status_code == 200
    data = case_resp_after.json()
    assert data["status"] == "recovered"
    assert data["recovered_amount"] == 199900

    # Step 4: Verify metrics via API
    metrics_resp = client.get("/api/metrics")
    assert metrics_resp.status_code == 200
    metrics_data = metrics_resp.json()
    assert metrics_data["cases_recovered"] >= 1
    assert metrics_data["total_recovered_amount"] >= 199900
