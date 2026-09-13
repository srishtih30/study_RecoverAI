"""
raw Razorpay webhook payload -> app.domain.events.NormalizedEvent

This is the ONLY place raw Razorpay JSON should be parsed for downstream
use. Everything past this point (classifier, case_service, decision_engine,
audit_service) must consume `NormalizedEvent`, never this payload shape.

TODO(AG): verify Razorpay test-mode behavior for this operation — the exact
payload shape below is based on Razorpay's public webhook documentation
structure (entity/event/contains/payload/created_at) but has not been
validated against a live test-mode delivery. In particular:
  * Confirm the provider event id source: Razorpay sends an
    `X-Razorpay-Event-Id` header on webhook deliveries — this is used here
    as the idempotency key in preference to any body field, since older
    Razorpay payloads do not reliably include a stable event id in the body.
  * Confirm exact field names for `error_code` / `error_description` on the
    payment entity for each event type this system handles
    (payment.failed, subscription.charged, subscription.pending,
    subscription.halted).
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from app.domain.enums import EventSource, NormalizedEventType
from app.domain.events import NormalizedEvent

# Razorpay event string -> our internal event type.
RAZORPAY_EVENT_TYPE_MAP: dict[str, NormalizedEventType] = {
    "payment.failed": NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED,
    "subscription.charged": NormalizedEventType.SUBSCRIPTION_CHARGED_SUCCESS,
    "subscription.pending": NormalizedEventType.SUBSCRIPTION_PENDING,
    "subscription.halted": NormalizedEventType.SUBSCRIPTION_HALTED,
}


def normalize_razorpay_payload(raw_body: bytes, *, event_id_header: Optional[str] = None) -> NormalizedEvent:
    payload: dict[str, Any] = json.loads(raw_body)

    razorpay_event = payload.get("event", "")
    event_type = RAZORPAY_EVENT_TYPE_MAP.get(razorpay_event, NormalizedEventType.UNKNOWN)

    payment_entity: dict[str, Any] = payload.get("payload", {}).get("payment", {}).get("entity", {}) or {}
    subscription_entity: dict[str, Any] = payload.get("payload", {}).get("subscription", {}).get("entity", {}) or {}

    provider_event_id = event_id_header or payload.get("id") or _fallback_event_id(raw_body)

    created_at_epoch = payload.get("created_at")
    occurred_at = (
        datetime.fromtimestamp(created_at_epoch, tz=timezone.utc) if created_at_epoch else datetime.now(timezone.utc)
    )

    return NormalizedEvent(
        provider_event_id=str(provider_event_id),
        event_type=event_type,
        source=EventSource.RAZORPAY_WEBHOOK,
        subscription_id=subscription_entity.get("id") or payment_entity.get("subscription_id"),
        payment_id=payment_entity.get("id"),
        customer_id=payment_entity.get("customer_id") or subscription_entity.get("customer_id"),
        amount=payment_entity.get("amount") or subscription_entity.get("charge_amount") or subscription_entity.get("current_amount"),
        currency=payment_entity.get("currency", "INR"),
        failure_code=payment_entity.get("error_code"),
        failure_description=payment_entity.get("error_description"),
        occurred_at=occurred_at,
        raw_payload=payload,
    )


def _fallback_event_id(raw_body: bytes) -> str:
    """
    Last-resort idempotency key when neither the X-Razorpay-Event-Id header
    nor a body "id" field is present. A content hash is NOT a substitute for
    a real provider event id (two distinct events could theoretically hash
    the same content in edge cases) — this exists so the pipeline degrades
    safely instead of crashing, not as the intended long-term behavior.
    TODO(AG): remove this fallback once the real header/field is confirmed
    to always be present in Razorpay test-mode deliveries.
    """
    return f"content_hash_{hashlib.sha256(raw_body).hexdigest()[:32]}"
