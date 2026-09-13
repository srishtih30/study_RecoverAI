"""
Normalized internal event model.

No application code outside `app/integrations/razorpay/event_normalizer.py`
(and the simulator, which fabricates events in this same shape) should
construct or depend on raw Razorpay webhook JSON. Everything downstream —
the classifier, case service, decision engine, audit service — consumes
`NormalizedEvent`, never the provider payload.

Flow: raw Razorpay payload -> event_normalizer.normalize() -> NormalizedEvent
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import EventSource, NormalizedEventType


class NormalizedEvent(BaseModel):
    """A provider-agnostic representation of a revenue-at-risk event.

    `raw_payload` is retained only for debugging/audit purposes (e.g. to
    inspect exactly what Razorpay sent when investigating an incident) — it
    must never be read by business logic. If you find yourself reaching into
    `raw_payload` from the classifier, decision engine, or case service,
    that's a sign a field is missing from this model and should be added
    here instead.
    """

    model_config = ConfigDict(frozen=True)

    provider_event_id: str = Field(
        ..., description="Razorpay's unique event id (x-razorpay-event-id / payload.id). Used for idempotency."
    )
    event_type: NormalizedEventType
    source: EventSource = Field(
        ..., description="Distinguishes real Razorpay webhooks from simulator-generated events."
    )

    subscription_id: Optional[str] = None
    payment_id: Optional[str] = None
    customer_id: Optional[str] = None

    amount: Optional[int] = Field(
        default=None, description="Amount in the smallest currency unit (paise for INR), matching Razorpay convention."
    )
    currency: str = "INR"

    failure_code: Optional[str] = Field(
        default=None, description="Raw Razorpay error code (e.g. 'card_declined'), passed through for classification."
    )
    failure_description: Optional[str] = Field(
        default=None, description="Free-text failure reason from Razorpay, used for LLM-fallback classification."
    )

    occurred_at: datetime = Field(..., description="Event timestamp as reported by the provider (or simulator).")

    raw_payload: Optional[dict[str, Any]] = Field(
        default=None, description="Original payload, retained for debugging/audit only. Do not consume in business logic."
    )
