from __future__ import annotations

from datetime import datetime, timezone

from app.domain.enums import CaseStatus, EventSource, FailureCategory, NormalizedEventType
from app.domain.events import NormalizedEvent
from app.models.case import RecoveryCase
from app.services.simulator_service import run_simulation
from app.services.webhook_orchestrator import process_event


def test_simulator_batch_produces_measurable_outcomes(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.recovery_executor._enqueue_execution",
        lambda attempt_id, eta=None: None,
    )
    case_ids = run_simulation(db_session, count=10)
    assert len(case_ids) == 10

    cases = db_session.query(RecoveryCase).filter(RecoveryCase.id.in_(case_ids)).all()
    assert all(case.source == EventSource.SIMULATOR for case in cases)
    assert any(case.status == CaseStatus.RECOVERED for case in cases)
    assert any(case.status == CaseStatus.HALTED for case in cases)
    assert any(case.status in {CaseStatus.WAITING_FOR_RETRY, CaseStatus.WAITING_FOR_CUSTOMER, CaseStatus.ESCALATED} for case in cases)


def test_subscription_halted_closes_matching_open_case(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.recovery_executor._enqueue_execution",
        lambda attempt_id, eta=None: None,
    )
    failure = NormalizedEvent(
        provider_event_id="sim_failure_halt_1",
        event_type=NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED,
        source=EventSource.SIMULATOR,
        subscription_id="sub_halt_test",
        customer_id="cust_halt_test",
        amount=99900,
        currency="INR",
        failure_code="card_declined",
        failure_description="card declined",
        occurred_at=datetime.now(timezone.utc),
    )
    created = process_event(db_session, failure)
    assert created["case_id"]

    halted = NormalizedEvent(
        provider_event_id="sim_halted_1",
        event_type=NormalizedEventType.SUBSCRIPTION_HALTED,
        source=EventSource.SIMULATOR,
        subscription_id="sub_halt_test",
        customer_id="cust_halt_test",
        amount=99900,
        currency="INR",
        occurred_at=datetime.now(timezone.utc),
    )
    result = process_event(db_session, halted)
    case = db_session.query(RecoveryCase).filter(RecoveryCase.id == result["case_id"]).one()
    assert case.status == CaseStatus.HALTED
    assert case.resolved_at is not None


def test_contact_cap_halts_repeated_customer_contacts(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.recovery_executor._enqueue_execution",
        lambda attempt_id, eta=None: None,
    )
    subscription_id = "sub_contact_cap"
    for idx in range(3):
        event = NormalizedEvent(
            provider_event_id=f"contact_cap_{idx}",
            event_type=NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED,
            source=EventSource.SIMULATOR,
            subscription_id=subscription_id,
            customer_id="cust_contact_cap",
            amount=49900,
            currency="INR",
            failure_code="card_declined",
            failure_description="card declined",
            occurred_at=datetime.now(timezone.utc),
        )
        result = process_event(db_session, event)

    case = db_session.query(RecoveryCase).filter(RecoveryCase.id == result["case_id"]).one()
    assert case.status == CaseStatus.HALTED
    assert len(case.attempts) == 3
    assert case.attempts[-1].action_type.value == "halt"
