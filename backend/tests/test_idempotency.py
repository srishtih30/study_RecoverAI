"""Idempotency foundation tests (PRD NFR: duplicate webhook deliveries must not trigger duplicate processing)."""

from datetime import datetime, timezone

from app.domain.enums import EventSource, NormalizedEventType
from app.domain.events import NormalizedEvent
from app.services import idempotency


def _event(provider_event_id: str) -> NormalizedEvent:
    return NormalizedEvent(
        provider_event_id=provider_event_id,
        event_type=NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED,
        source=EventSource.SIMULATOR,
        occurred_at=datetime.now(timezone.utc),
    )


def test_first_delivery_is_not_a_duplicate(db_session):
    is_duplicate, row = idempotency.check_and_record(db_session, _event("evt_idem_1"))
    assert is_duplicate is False
    assert row.provider_event_id == "evt_idem_1"


def test_second_delivery_of_same_event_id_is_a_duplicate(db_session):
    idempotency.check_and_record(db_session, _event("evt_idem_2"))
    is_duplicate, row = idempotency.check_and_record(db_session, _event("evt_idem_2"))
    assert is_duplicate is True
    assert row.provider_event_id == "evt_idem_2"


def test_different_event_ids_are_both_processed(db_session):
    is_dup_a, _ = idempotency.check_and_record(db_session, _event("evt_idem_3a"))
    is_dup_b, _ = idempotency.check_and_record(db_session, _event("evt_idem_3b"))
    assert is_dup_a is False
    assert is_dup_b is False
