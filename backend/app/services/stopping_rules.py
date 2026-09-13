"""
Stopping rules engine (PRD F5) — the hard limits that guarantee boundedness.

Every case must terminate in RECOVERED / HALTED / ESCALATED. This module is
what enforces that: it is evaluated BEFORE the decision engine runs, and its
result (`stopping_rule_triggered`, `stopping_rule_reason`) is passed into
`DecisionContext` so the decision engine can act on it without needing to
re-derive the same logic (or, worse, a slightly different version of it).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.domain.decision import StoppingRuleSnapshot
from app.domain.enums import FailureCategory
from app.models.case import RecoveryCase
from app.models.stopping_rule import StoppingRuleConfig


DEFAULT_STOPPING_RULES: list[dict[str, Any]] = [
    {
        "failure_category": FailureCategory.RETRIABLE_TECHNICAL.value,
        "max_retries": 4,
        "retry_intervals_hours": [2, 6, 24, 72],
        "max_days_open": 5,
        "max_contacts": 2,
        "opt_out_respected": True,
    },
    {
        "failure_category": FailureCategory.INSUFFICIENT_FUNDS.value,
        "max_retries": 3,
        "retry_intervals_hours": [24, 72, 168],
        "max_days_open": 14,
        "max_contacts": 2,
        "opt_out_respected": True,
    },
    {
        "failure_category": FailureCategory.CARD_ISSUE.value,
        "max_retries": 2,
        "retry_intervals_hours": [24, 72],
        "max_days_open": 10,
        "max_contacts": 2,
        "opt_out_respected": True,
    },
    {
        "failure_category": FailureCategory.CUSTOMER_ACTION_NEEDED.value,
        "max_retries": 2,
        "retry_intervals_hours": [12, 48],
        "max_days_open": 7,
        "max_contacts": 2,
        "opt_out_respected": True,
    },
    {
        "failure_category": FailureCategory.UNKNOWN.value,
        "max_retries": 1,
        "retry_intervals_hours": [24],
        "max_days_open": 3,
        "max_contacts": 1,
        "opt_out_respected": True,
    },
]


def get_stopping_rule(db: Session, failure_category: FailureCategory) -> StoppingRuleSnapshot:
    """Loads the configured rule for a category, falling back to Settings defaults if none is seeded yet."""
    row: Optional[StoppingRuleConfig] = (
        db.query(StoppingRuleConfig).filter(StoppingRuleConfig.failure_category == failure_category).first()
    )
    if row is not None:
        return StoppingRuleSnapshot(
            max_retries=row.max_retries,
            retry_intervals_hours=list(row.retry_intervals_hours or []),
            max_days_open=row.max_days_open,
            max_contacts=row.max_contacts,
            opt_out_respected=row.opt_out_respected,
        )

    settings = get_settings()
    return StoppingRuleSnapshot(
        max_retries=settings.default_max_retry_attempts,
        retry_intervals_hours=[2, 24, 72][: settings.default_max_retry_attempts] or [2],
        max_days_open=settings.default_max_days_open,
        max_contacts=2,
        opt_out_respected=True,
    )


def evaluate(case: RecoveryCase, rule: StoppingRuleSnapshot) -> tuple[bool, Optional[str]]:
    """Returns (triggered, human_readable_reason)."""
    if rule.opt_out_respected and case.opted_out:
        return True, "Customer opted out; halting immediately per stopping rules."

    if case.retry_count >= rule.max_retries:
        return True, f"Max retries reached ({case.retry_count}/{rule.max_retries})."

    from app.domain.enums import RecoveryActionType
    contact_actions = {
        RecoveryActionType.SEND_PAYMENT_UPDATE_LINK,
        RecoveryActionType.NOTIFY_CUSTOMER,
    }
    contact_count = sum(1 for attempt in case.attempts if attempt.action_type in contact_actions)
    if contact_count >= rule.max_contacts:
        return True, f"Customer contact cap reached ({contact_count}/{rule.max_contacts})."

    days_open = (datetime.now(timezone.utc) - case.created_at.replace(tzinfo=timezone.utc)).days
    if days_open >= rule.max_days_open:
        return True, f"Case open for {days_open} days, exceeding max_days_open ({rule.max_days_open})."

    return False, None
