"""Tests for the normalized internal event model and the Razorpay normalizer/verifier."""

import hashlib
import hmac
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.domain.enums import EventSource, NormalizedEventType
from app.domain.events import NormalizedEvent
from app.integrations.razorpay.event_normalizer import normalize_razorpay_payload
from app.integrations.razorpay.webhook_verifier import verify_signature


def test_normalized_event_is_immutable():
    event = NormalizedEvent(
        provider_event_id="evt_1",
        event_type=NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED,
        source=EventSource.SIMULATOR,
        occurred_at=datetime.now(timezone.utc),
    )
    with pytest.raises(ValidationError):
        event.provider_event_id = "evt_2"  # type: ignore[misc]


def test_normalize_razorpay_payload_maps_payment_failed():
    payload = {
        "entity": "event",
        "event": "payment.failed",
        "created_at": 1735689600,
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_ABC123",
                    "amount": 99900,
                    "currency": "INR",
                    "error_code": "card_declined",
                    "error_description": "Card was declined by the issuing bank.",
                    "customer_id": "cust_XYZ",
                }
            },
            "subscription": {"entity": {"id": "sub_QWE789"}},
        },
    }
    raw_body = json.dumps(payload).encode("utf-8")

    event = normalize_razorpay_payload(raw_body, event_id_header="evt_header_1")

    assert event.provider_event_id == "evt_header_1"
    assert event.event_type == NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED
    assert event.source == EventSource.RAZORPAY_WEBHOOK
    assert event.subscription_id == "sub_QWE789"
    assert event.payment_id == "pay_ABC123"
    assert event.customer_id == "cust_XYZ"
    assert event.amount == 99900
    assert event.failure_code == "card_declined"
    assert event.raw_payload == payload


def test_normalize_razorpay_payload_falls_back_to_content_hash_without_event_id():
    payload = {"event": "payment.failed", "payload": {}}
    raw_body = json.dumps(payload).encode("utf-8")

    event = normalize_razorpay_payload(raw_body)

    assert event.provider_event_id.startswith("content_hash_")


def test_webhook_signature_verification_matches_valid_hmac():
    secret = "test_secret"
    body = b'{"event": "payment.failed"}'
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()

    assert verify_signature(raw_body=body, signature=signature, secret=secret) is True


def test_webhook_signature_verification_rejects_bad_signature():
    assert verify_signature(raw_body=b"{}", signature="not-a-real-signature", secret="test_secret") is False


def test_webhook_signature_verification_fails_closed_without_secret():
    assert verify_signature(raw_body=b"{}", signature="anything", secret="") is False
