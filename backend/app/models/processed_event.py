"""
ProcessedWebhookEvent — idempotency foundation (PRD NFR: Idempotency).

Flow (implemented in app/services/idempotency.py):
    receive event -> check provider_event_id against this table
    -> already present? ignore / acknowledge duplicate, no new case/attempt
    -> not present? insert a row (unique constraint enforces this atomically),
       then process the event once.

The unique constraint on `provider_event_id` is what actually prevents
duplicate processing under concurrent delivery — the "check then insert"
logic in idempotency.py relies on the DB rejecting a second insert, not on
an application-level check alone (which would race).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import EventSource, NormalizedEventType
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProcessedWebhookEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "processed_webhook_events"

    provider_event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    event_type: Mapped[NormalizedEventType] = mapped_column(
        SAEnum(NormalizedEventType, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32), nullable=False
    )
    source: Mapped[EventSource] = mapped_column(
        SAEnum(EventSource, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32), nullable=False
    )
    case_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ProcessedWebhookEvent provider_event_id={self.provider_event_id}>"
