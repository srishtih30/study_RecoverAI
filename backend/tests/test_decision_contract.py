"""
Decision engine contract tests — pure input -> output, no DB/Razorpay/Celery
involved (see app/domain/decision.py and app/services/decision_engine.py).
"""

from datetime import datetime, timezone

import pytest

from app.domain.decision import CaseSnapshot, DecisionContext, StoppingRuleSnapshot
from app.domain.enums import CaseStatus, FailureCategory, RecoveryActionType
from app.services.decision_engine import decide_next_action


def _base_case_snapshot(**overrides) -> CaseSnapshot:
    defaults = dict(
        id="case-1",
        status=CaseStatus.OPEN,
        failure_category=FailureCategory.UNKNOWN,
        amount=99900,
        currency="INR",
        retry_count=0,
        opted_out=False,
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return CaseSnapshot(**defaults)


def _base_rule(**overrides) -> StoppingRuleSnapshot:
    defaults = dict(max_retries=3, retry_intervals_hours=[2, 24, 72], max_days_open=7, opt_out_respected=True)
    defaults.update(overrides)
    return StoppingRuleSnapshot(**defaults)


@pytest.mark.parametrize(
    "category,expected_action,expected_status",
    [
        (FailureCategory.RETRIABLE_TECHNICAL, RecoveryActionType.RETRY_LATER, CaseStatus.WAITING_FOR_RETRY),
        (FailureCategory.CARD_ISSUE, RecoveryActionType.SEND_PAYMENT_UPDATE_LINK, CaseStatus.WAITING_FOR_CUSTOMER),
        (FailureCategory.INSUFFICIENT_FUNDS, RecoveryActionType.RETRY_LATER, CaseStatus.WAITING_FOR_RETRY),
        (FailureCategory.CUSTOMER_ACTION_NEEDED, RecoveryActionType.NOTIFY_CUSTOMER, CaseStatus.WAITING_FOR_CUSTOMER),
        (FailureCategory.UNKNOWN, RecoveryActionType.ESCALATE, CaseStatus.ESCALATED),
    ],
)
def test_decide_next_action_maps_category_to_action(category, expected_action, expected_status):
    context = DecisionContext(
        case=_base_case_snapshot(failure_category=category),
        failure_category=category,
        history=[],
        stopping_rule=_base_rule(),
        stopping_rule_triggered=False,
    )
    decision = decide_next_action(context)
    assert decision.action == expected_action
    assert decision.next_status == expected_status
    assert decision.reason  # explainability: every decision needs a human-readable reason


def test_stopping_rule_triggered_always_halts_regardless_of_category():
    context = DecisionContext(
        case=_base_case_snapshot(retry_count=5, failure_category=FailureCategory.RETRIABLE_TECHNICAL),
        failure_category=FailureCategory.RETRIABLE_TECHNICAL,
        history=[],
        stopping_rule=_base_rule(max_retries=3),
        stopping_rule_triggered=True,
        stopping_rule_reason="Max retries reached (5/3).",
    )
    decision = decide_next_action(context)
    assert decision.action == RecoveryActionType.HALT
    assert decision.next_status == CaseStatus.HALTED
    assert "Max retries" in decision.reason


def test_decision_engine_never_returns_execute_at_in_the_past_for_delayed_actions():
    context = DecisionContext(
        case=_base_case_snapshot(failure_category=FailureCategory.INSUFFICIENT_FUNDS),
        failure_category=FailureCategory.INSUFFICIENT_FUNDS,
        history=[],
        stopping_rule=_base_rule(),
        stopping_rule_triggered=False,
    )
    decision = decide_next_action(context)
    assert decision.execute_at is not None
    assert decision.execute_at > datetime.now(timezone.utc)
