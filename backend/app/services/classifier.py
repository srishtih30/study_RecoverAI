"""
Failure classification (PRD F2).

Rule: deterministic rules run FIRST. The LLM fallback (see
app/integrations/llm/classifier_fallback.py) is only consulted when the
deterministic map does not recognize `event.failure_code`. Do not call the
LLM when a deterministic rule already produced an answer — it's slower,
costs money, and is explicitly against the mandatory architecture rules.

TODO(AG): the DETERMINISTIC_FAILURE_CODE_MAP below is a starting point, not
verified against real Razorpay test-mode failure codes. Confirm actual
codes Razorpay test mode emits (payment.failed / subscription.* payloads)
and expand this map — see Risks & Open Questions in the PRD ("Razorpay test
mode can't simulate every failure type needed").
TODO(AG): verify Razorpay test-mode behavior for this operation.
"""

from __future__ import annotations

from app.domain.enums import FailureCategory
from app.domain.events import NormalizedEvent
from app.integrations.llm.classifier_fallback import classify_with_llm

# Deterministic mapping: Razorpay error code -> FailureCategory.
# Extend this first before ever reaching for the LLM fallback.
DETERMINISTIC_FAILURE_CODE_MAP: dict[str, FailureCategory] = {
    "bank_timeout": FailureCategory.RETRIABLE_TECHNICAL,
    "gateway_error": FailureCategory.RETRIABLE_TECHNICAL,
    "network_error": FailureCategory.RETRIABLE_TECHNICAL,
    "card_declined": FailureCategory.CARD_ISSUE,
    "expired_card": FailureCategory.CARD_ISSUE,
    "invalid_card": FailureCategory.CARD_ISSUE,
    "insufficient_funds": FailureCategory.INSUFFICIENT_FUNDS,
    "authentication_failed": FailureCategory.CUSTOMER_ACTION_NEEDED,
    "otp_timeout": FailureCategory.CUSTOMER_ACTION_NEEDED,
}


def classify_failure(event: NormalizedEvent) -> FailureCategory:
    """Deterministic-first, LLM-fallback classification. Returns FailureCategory.UNKNOWN if neither resolves it."""
    code = (event.failure_code or "").strip().lower()

    if code in DETERMINISTIC_FAILURE_CODE_MAP:
        return DETERMINISTIC_FAILURE_CODE_MAP[code]

    # Deterministic rules were insufficient (unrecognized/missing code) —
    # this is the ONLY point in the codebase that should reach for the LLM.
    return classify_with_llm(event)
