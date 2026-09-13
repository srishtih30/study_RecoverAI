"""
Idempotency foundation (PRD NFR: duplicate webhook deliveries must not
trigger duplicate retries).

Flow:
    receive event -> check_and_record(event) -> (is_duplicate, row)
        is_duplicate=True  -> caller acknowledges and stops, no case/attempt created
        is_duplicate=False -> caller proceeds to classify/decide/act once

The actual guarantee comes from the UNIQUE constraint on
`processed_webhook_events.provider_event_id` (see app/models/processed_event.py),
not from the SELECT-then-INSERT check alone — under concurrent delivery the
second INSERT will raise IntegrityError, which this function treats as "was
a duplicate". A single-process hackathon deployment will rarely hit that
race, but the schema is already race-safe for when Antigravity scales this
to multiple workers.

TODO(AG): consider wrapping this in `db.begin_nested()` (a SAVEPOINT) if
`check_and_record` is ever called inside a larger already-open transaction,
so the IntegrityError rollback doesn't invalidate unrelated pending writes
on the same session.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.domain.events import NormalizedEvent
from app.models.processed_event import ProcessedWebhookEvent


def check_and_record(db: Session, event: NormalizedEvent) -> tuple[bool, ProcessedWebhookEvent]:
    """Returns (is_duplicate, ProcessedWebhookEvent row). Never raises IntegrityError to the caller."""
    existing = (
        db.query(ProcessedWebhookEvent)
        .filter(ProcessedWebhookEvent.provider_event_id == event.provider_event_id)
        .first()
    )
    if existing is not None:
        return True, existing

    row = ProcessedWebhookEvent(
        provider_event_id=event.provider_event_id,
        event_type=event.event_type,
        source=event.source,
        processed_at=datetime.now(timezone.utc),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        # Lost a race with a concurrent delivery of the same event.
        db.rollback()
        existing = (
            db.query(ProcessedWebhookEvent)
            .filter(ProcessedWebhookEvent.provider_event_id == event.provider_event_id)
            .first()
        )
        assert existing is not None  # the unique constraint guarantees this
        return True, existing

    db.refresh(row)
    return False, row


def attach_case_id(db: Session, processed_event: ProcessedWebhookEvent, case_id: str) -> None:
    """Backfill case_id onto a ProcessedWebhookEvent once the case is known."""
    processed_event.case_id = case_id
    db.add(processed_event)
    db.commit()
