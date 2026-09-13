"""
Razorpay webhook ingestion (PRD F1).

This route is deliberately thin: it reads the raw request body (needed for
signature verification, which requires the exact bytes Razorpay sent) and
hands off immediately to app.services.webhook_orchestrator. All actual
verify -> normalize -> dedupe -> classify -> decide -> audit logic lives in
the service layer per AGENTS.md — do not add business logic here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.webhook import WebhookAckResponse
from app.services import webhook_orchestrator
from app.services.webhook_orchestrator import InvalidWebhookSignatureError

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.post("/razorpay", response_model=WebhookAckResponse)
async def receive_razorpay_webhook(request: Request, db: Session = Depends(get_db)) -> WebhookAckResponse:
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    # TODO(AG): verify Razorpay test-mode behavior for this operation — confirm
    # "X-Razorpay-Event-Id" is the correct header name for the provider event id.
    event_id_header = request.headers.get("X-Razorpay-Event-Id")

    try:
        result = webhook_orchestrator.handle_raw_webhook(
            db, raw_body=raw_body, signature=signature, event_id_header=event_id_header
        )
    except InvalidWebhookSignatureError:
        # Reject invalid signatures outright — do not process, do not 500.
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    return WebhookAckResponse(**result)
