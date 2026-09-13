"""
Webhook orchestrator — the main system flow described in the PRD and
ARCHITECTURE.md / DATA_FLOW.md:

    Razorpay webhook
        -> verify webhook
        -> normalize event
        -> deduplicate event
        -> classify failure
        -> load/create recovery case
        -> check stopping rules
        -> decide next action
        -> schedule or execute action
        -> audit everything
        -> expose updated state to dashboard (via the cases/metrics APIs)

Two entry points:
  * `handle_raw_webhook(db, raw_body, signature)` — real Razorpay webhooks.
    Verifies the signature, normalizes the raw payload, then calls
    `process_event`.
  * `process_event(db, event)` — the shared pipeline. Also called directly
    by `simulator_service` with SIMULATOR-sourced events, so simulated and
    real traffic can never silently diverge in behavior.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.decision import DecisionContext
from app.domain.enums import AuditActor, AuditEventType, CaseStatus, NormalizedEventType
from app.domain.events import NormalizedEvent
from app.integrations.razorpay.event_normalizer import normalize_razorpay_payload
from app.integrations.razorpay.webhook_verifier import verify_signature
from app.services import audit_service, case_service, idempotency, stopping_rules
from app.services.classifier import classify_failure
from app.services.decision_engine import decide_next_action
from app.services.recovery_executor import schedule_or_execute


class InvalidWebhookSignatureError(Exception):
    """Raised when a raw webhook's signature does not match. The API layer turns this into an HTTP 400."""


def handle_raw_webhook(
    db: Session, *, raw_body: bytes, signature: str, event_id_header: str | None = None
) -> dict[str, Any]:
    settings = get_settings()

    if not verify_signature(raw_body=raw_body, signature=signature, secret=settings.razorpay_webhook_secret):
        audit_service.record_event(
            db,
            event_type=AuditEventType.WEBHOOK_SIGNATURE_INVALID,
            actor=AuditActor.SYSTEM,
            description="Rejected webhook with invalid signature.",
        )
        raise InvalidWebhookSignatureError()

    event = normalize_razorpay_payload(raw_body, event_id_header=event_id_header)
    return process_event(db, event)


def process_event(db: Session, event: NormalizedEvent) -> dict[str, Any]:
    """Shared pipeline for both real Razorpay webhooks and simulator-generated events."""
    audit_service.record_event(
        db,
        event_type=AuditEventType.WEBHOOK_RECEIVED,
        actor=AuditActor.SYSTEM if event.source.value == "razorpay_webhook" else AuditActor.SIMULATOR,
        description=f"Received {event.event_type.value} (provider_event_id={event.provider_event_id}, source={event.source.value})",
        metadata={"raw_payload": event.raw_payload} if event.raw_payload else None,
    )

    is_duplicate, processed = idempotency.check_and_record(db, event)
    if is_duplicate:
        audit_service.record_event(
            db,
            event_type=AuditEventType.WEBHOOK_DUPLICATE_IGNORED,
            actor=AuditActor.SYSTEM,
            description=f"Duplicate event ignored (provider_event_id={event.provider_event_id}).",
            case_id=processed.case_id,
        )
        return {"status": "ok", "provider_event_id": event.provider_event_id, "duplicate": True, "case_id": processed.case_id}

    if event.event_type == NormalizedEventType.SUBSCRIPTION_CHARGED_SUCCESS:
        open_case = case_service.find_open_case_for_event(db, event)
        if open_case is not None:
            idempotency.attach_case_id(db, processed, open_case.id)
            recovered_case = case_service.mark_case_recovered(
                db,
                open_case,
                recovered_amount=event.amount,
                resolved_at=event.occurred_at,
            )
            audit_service.record_event(
                db,
                case_id=recovered_case.id,
                event_type=AuditEventType.CASE_RECOVERED,
                actor=AuditActor.SYSTEM if event.source.value == "razorpay_webhook" else AuditActor.SIMULATOR,
                description=f"Case recovered via successful charge (recovered_amount={recovered_case.recovered_amount}, event_id={event.provider_event_id}).",
                metadata={
                    "provider_event_id": event.provider_event_id,
                    "payment_id": event.payment_id,
                    "recovered_amount": recovered_case.recovered_amount,
                    "currency": recovered_case.currency,
                },
            )
            return {"status": "ok", "provider_event_id": event.provider_event_id, "duplicate": False, "case_id": recovered_case.id}

        existing_case = (
            case_service.get_latest_case_for_subscription(db, event.subscription_id)
            if event.subscription_id
            else None
        )
        matched_case_id = existing_case.id if existing_case is not None else None
        if matched_case_id:
            idempotency.attach_case_id(db, processed, matched_case_id)

        description = (
            f"Acknowledged {event.event_type.value} for subscription {event.subscription_id}; "
            f"case is already terminal ({existing_case.status.value}). No action taken."
            if existing_case is not None
            else f"Acknowledged {event.event_type.value}; no active recovery case found for subscription {event.subscription_id}. No action taken."
        )
        audit_service.record_event(
            db,
            case_id=matched_case_id,
            event_type=AuditEventType.EVENT_NORMALIZED,
            actor=AuditActor.SYSTEM if event.source.value == "razorpay_webhook" else AuditActor.SIMULATOR,
            description=description,
            metadata={"provider_event_id": event.provider_event_id, "subscription_id": event.subscription_id},
        )
        return {"status": "ok", "provider_event_id": event.provider_event_id, "duplicate": False, "case_id": matched_case_id}

    if event.event_type == NormalizedEventType.SUBSCRIPTION_HALTED:
        open_case = case_service.find_open_case_for_event(db, event)
        if open_case is not None:
            idempotency.attach_case_id(db, processed, open_case.id)
            case_service.apply_decision_to_case(
                db, open_case, next_status=CaseStatus.HALTED, increment_retry=False
            )
            audit_service.record_event(
                db,
                case_id=open_case.id,
                event_type=AuditEventType.CASE_HALTED,
                actor=AuditActor.SYSTEM if event.source.value == "razorpay_webhook" else AuditActor.SIMULATOR,
                description="Razorpay reported the subscription as halted; recovery case halted.",
                metadata={"provider_event_id": event.provider_event_id},
            )
            return {"status": "ok", "provider_event_id": event.provider_event_id, "duplicate": False, "case_id": open_case.id}

        audit_service.record_event(
            db,
            event_type=AuditEventType.EVENT_NORMALIZED,
            actor=AuditActor.SYSTEM if event.source.value == "razorpay_webhook" else AuditActor.SIMULATOR,
            description="Acknowledged subscription_halted; no active recovery case matched.",
        )
        return {"status": "ok", "provider_event_id": event.provider_event_id, "duplicate": False, "case_id": None}

    if event.event_type != NormalizedEventType.SUBSCRIPTION_PAYMENT_FAILED:
        audit_service.record_event(
            db,
            event_type=AuditEventType.EVENT_NORMALIZED,
            actor=AuditActor.SYSTEM if event.source.value == "razorpay_webhook" else AuditActor.SIMULATOR,
            description=f"Acknowledged {event.event_type.value}; no recovery action required.",
        )
        return {"status": "ok", "provider_event_id": event.provider_event_id, "duplicate": False, "case_id": None}

    failure_category = classify_failure(event)

    case, created = case_service.get_or_create_case(db, event, failure_category)
    idempotency.attach_case_id(db, processed, case.id)

    audit_service.record_event(
        db,
        case_id=case.id,
        event_type=AuditEventType.CASE_CREATED if created else AuditEventType.CASE_UPDATED,
        actor=AuditActor.SYSTEM,
        description=f"{'Created' if created else 'Updated'} case for subscription {case.subscription_id}.",
    )
    audit_service.record_event(
        db,
        case_id=case.id,
        event_type=AuditEventType.FAILURE_CLASSIFIED,
        actor=AuditActor.AGENT,
        description=f"Classified failure as {failure_category.value}.",
        metadata={"failure_code": event.failure_code, "failure_description": event.failure_description},
    )

    rule = stopping_rules.get_stopping_rule(db, failure_category)
    triggered, reason = stopping_rules.evaluate(case, rule)
    if triggered:
        audit_service.record_event(
            db,
            case_id=case.id,
            event_type=AuditEventType.STOPPING_RULE_TRIGGERED,
            actor=AuditActor.SYSTEM,
            description=reason or "Stopping rule triggered.",
        )

    context = DecisionContext(
        case=case_service.to_snapshot(case),
        failure_category=failure_category,
        history=case_service.history_snapshots(case),
        stopping_rule=rule,
        stopping_rule_triggered=triggered,
        stopping_rule_reason=reason,
    )
    decision = decide_next_action(context)

    schedule_or_execute(db, case, decision)

    return {"status": "ok", "provider_event_id": event.provider_event_id, "duplicate": False, "case_id": case.id}
