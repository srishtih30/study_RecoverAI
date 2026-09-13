"""
Async webhook processing task.

NOTE on current wiring: `app/api/webhooks.py` currently calls
`webhook_orchestrator.handle_raw_webhook(...)` directly and synchronously
inside the FastAPI request handler, NOT via this task. That's a deliberate
hackathon-speed simplification — everything in the orchestrator pipeline is
bounded DB writes (no blocking external calls; Razorpay execution itself is
already deferred to `execute_action` below), so it comfortably fits inside
a webhook request/response cycle without a worker needing to be running for
the demo to work end-to-end.

This task exists so the switch to fully-async ingestion (matching the
PRD's "Webhook Receiver -> Event Queue -> Classifier -> ..." diagram) is a
one-line change when needed: swap the direct call in webhooks.py for
`process_webhook_task.delay(raw_body.decode("utf-8"), signature, event_id_header)`.
It calls the exact same orchestrator function — there is no second
implementation of the webhook flow to keep in sync.

TODO(AG): switch app/api/webhooks.py to enqueue this task instead of calling
the orchestrator inline, once you want webhook responses to return before
processing completes (e.g. under real Razorpay retry-on-timeout pressure).
"""

from __future__ import annotations

from typing import Optional

from app.db.session import SessionLocal
from app.services import webhook_orchestrator
from app.workers.celery_app import celery_app


@celery_app.task(name="process_webhook_task", bind=True, max_retries=3)
def process_webhook_task(self, raw_body: str, signature: str, event_id_header: Optional[str] = None) -> dict:
    db = SessionLocal()
    try:
        return webhook_orchestrator.handle_raw_webhook(
            db, raw_body=raw_body.encode("utf-8"), signature=signature, event_id_header=event_id_header
        )
    finally:
        db.close()
