"""LLM-assisted failure classification fallback (PRD F2).

Deterministic rules always run first. This module is only called for
unrecognized failure codes/free-text descriptions. Provider failures are
fail-closed: they return UNKNOWN and never block webhook processing.
"""

from __future__ import annotations

import json
import re

import httpx

from app.config import get_settings
from app.domain.enums import FailureCategory
from app.domain.events import NormalizedEvent

_ALLOWED = {category.value: category for category in FailureCategory}
_SYSTEM_PROMPT = """Classify a Razorpay payment/subscription failure into exactly one value:
retriable_technical, card_issue, insufficient_funds, customer_action_needed, unknown.
Return JSON only: {"category":"<value>"}. Do not add any other fields or prose."""


def _parse_category(text: str) -> FailureCategory:
    text = text.strip()
    try:
        value = json.loads(text).get("category", "")
    except (json.JSONDecodeError, AttributeError):
        match = re.search(
            r"retriable_technical|card_issue|insufficient_funds|customer_action_needed|unknown",
            text.lower(),
        )
        value = match.group(0) if match else ""
    return _ALLOWED.get(str(value).lower(), FailureCategory.UNKNOWN)


def classify_with_llm(event: NormalizedEvent) -> FailureCategory:
    settings = get_settings()
    if settings.llm_provider == "none" or not settings.llm_api_key:
        return FailureCategory.UNKNOWN

    user_text = (
        f"failure_code={event.failure_code or 'missing'}\n"
        f"failure_description={event.failure_description or 'missing'}"
    )

    try:
        with httpx.Client(timeout=4.0) as client:
            if settings.llm_provider == "openai":
                model = settings.llm_model or "gpt-4o-mini"
                response = client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                    json={
                        "model": model,
                        "temperature": 0,
                        "max_tokens": 40,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPT},
                            {"role": "user", "content": user_text},
                        ],
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return _parse_category(content)

            if settings.llm_provider == "anthropic":
                model = settings.llm_model or "claude-3-5-haiku-latest"
                response = client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.llm_api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": model,
                        "max_tokens": 40,
                        "temperature": 0,
                        "system": _SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": user_text}],
                    },
                )
                response.raise_for_status()
                content = response.json()["content"][0]["text"]
                return _parse_category(content)
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        return FailureCategory.UNKNOWN

    return FailureCategory.UNKNOWN
