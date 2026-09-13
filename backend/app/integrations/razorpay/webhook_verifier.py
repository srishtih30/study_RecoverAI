"""
Razorpay webhook signature verification.

Razorpay signs webhook payloads with HMAC-SHA256 of the exact raw request
body, using the webhook secret configured in the Razorpay dashboard, and
sends the hex digest in the `X-Razorpay-Signature` header. This must be
computed over the raw bytes (not a re-serialized/parsed-then-dumped version)
or the signature will never match.

TODO(AG): verify Razorpay test-mode behavior for this operation — confirm
the header name, digest encoding, and whether the official `razorpay` SDK's
`Utility.verify_webhook_signature` should be used instead of this
hand-rolled HMAC comparison (it's equivalent, but the SDK is the
canonical source and may add validations, e.g. timestamp/replay checks).
"""

from __future__ import annotations

import hashlib
import hmac


def verify_signature(*, raw_body: bytes, signature: str, secret: str) -> bool:
    if not secret:
        # No webhook secret configured — fail closed rather than silently
        # accepting unsigned requests. Set RAZORPAY_WEBHOOK_SECRET in .env.
        return False
    if not signature:
        return False

    expected = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
