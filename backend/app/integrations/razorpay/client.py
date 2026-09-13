"""Razorpay API client wrapper.

Only this module constructs/uses the Razorpay SDK. RecoverAI is test-mode
only. Razorpay does not expose a general subscription "retry now" API; a
pending subscription is retried by Razorpay and recovery is confirmed only
when a later subscription.charged webhook arrives. Payment Links are used
for customer-driven recovery.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Optional

import razorpay

from app.config import get_settings


class RazorpayConfigurationError(RuntimeError):
    pass


class RazorpayClient:
    def __init__(self, key_id: str, key_secret: str) -> None:
        self._sdk = razorpay.Client(auth=(key_id, key_secret)) if key_id and key_secret else None

    def _require_sdk(self):
        if self._sdk is None:
            raise RazorpayConfigurationError("Razorpay test credentials are not configured.")
        return self._sdk

    def retry_subscription_charge(self, subscription_id: str) -> dict[str, Any]:
        """Validate the subscription and wait for Razorpay's bounded auto-retry.

        Razorpay's documented subscription flow retries pending subscriptions
        automatically; there is no generic public API equivalent of the
        Dashboard's manual `Attempt Charge` action. We therefore never fake a
        successful payment here. A later subscription.charged webhook is the
        source of truth for actual recovery.
        """
        sdk = self._require_sdk()
        subscription = sdk.subscription.fetch(subscription_id)
        status = str(subscription.get("status", "unknown"))
        if status not in {"pending", "active", "authenticated"}:
            raise RuntimeError(f"Subscription {subscription_id} is not retryable in status={status}.")
        return {
            "status": "awaiting_provider_retry",
            "subscription_id": subscription_id,
            "subscription_status": status,
            "payment_id": None,
        }

    def create_payment_update_link(
        self,
        subscription_id: str,
        customer_id: Optional[str],
        *,
        amount: int,
        currency: str = "INR",
    ) -> dict[str, Any]:
        sdk = self._require_sdk()
        payload: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "reference_id": f"recoverai-{subscription_id}"[:40],
            "description": f"RecoverAI payment recovery for subscription {subscription_id}",
            "notify": {"sms": False, "email": False},
            "notes": {"recoverai_subscription_id": subscription_id},
        }
        # Payment Links do not require a customer id. Keeping it in notes
        # preserves traceability without assuming contact details are available.
        if customer_id:
            payload["notes"]["recoverai_customer_id"] = customer_id
        result = sdk.payment_link.create(payload)
        return {
            "status": result.get("status", "created"),
            "id": result.get("id"),
            "link": result.get("short_url"),
        }

    def notify_customer(self, customer_id: Optional[str], *, reason: str) -> dict[str, Any]:
        """Record notification hand-off semantics without fabricating delivery.

        Razorpay subscription notifications are configured on the merchant
        account rather than sent through a general SDK method. If the product
        needs bespoke SMS/email, configure a dedicated provider in a future
        extension. Returning `provider_managed` is intentionally not a claim
        that an SMS/email was delivered.
        """
        return {"status": "provider_managed", "customer_id": customer_id, "reason": reason}


@lru_cache
def get_razorpay_client() -> RazorpayClient:
    settings = get_settings()
    return RazorpayClient(settings.razorpay_key_id, settings.razorpay_key_secret)
