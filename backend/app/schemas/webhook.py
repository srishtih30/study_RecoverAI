"""
Webhook ingestion response contract.

Note: the REQUEST body for the Razorpay webhook is intentionally NOT a
typed Pydantic schema — it's raw Razorpay JSON, read as bytes so the exact
payload can be used for signature verification (see app/api/webhooks.py and
app/integrations/razorpay/webhook_verifier.py). Only the response is typed.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class WebhookAckResponse(BaseModel):
    status: str = "ok"
    provider_event_id: Optional[str] = None
    duplicate: bool = False
    case_id: Optional[str] = None
