"""
Decision engine — pure function, no side effects.

    decide_next_action(context: DecisionContext) -> Decision

MUST NOT:
  * call Razorpay (see app/integrations/razorpay/)
  * send notifications
  * schedule Celery jobs
  * write to the database
It only reads the DecisionContext it is given and returns a Decision. The
caller (webhook_orchestrator) is responsible for every side effect: applying
the decision to the case, creating a RecoveryAttempt, scheduling the Celery
task, and writing the audit entry.

This is a minimal placeholder strategy — it implements the exact category ->
action mapping from PRD Section 6.1 so the pipeline is genuinely functional
end-to-end, but the retry-interval tuning, payday-adjacent timing, and
customer-messaging content are all left as TODOs for Antigravity to refine.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.domain.decision import Decision, DecisionContext
from app.domain.enums import CaseStatus, FailureCategory, RecoveryActionType


def decide_next_action(context: DecisionContext) -> Decision:
    if context.stopping_rule_triggered:
        return Decision(
            action=RecoveryActionType.HALT,
            next_status=CaseStatus.HALTED,
            reason=context.stopping_rule_reason or "Stopping rule triggered.",
        )

    category = context.failure_category
    now = datetime.now(timezone.utc)

    if category == FailureCategory.RETRIABLE_TECHNICAL:
        intervals = context.stopping_rule.retry_intervals_hours or [2]
        interval_index = min(context.case.retry_count, len(intervals) - 1)
        delay_hours = max(0, int(intervals[interval_index]))
        return Decision(
            action=RecoveryActionType.RETRY_LATER,
            next_status=CaseStatus.WAITING_FOR_RETRY,
            reason=f"Retriable technical failure — scheduling bounded retry in {delay_hours}h.",
            execute_at=now + timedelta(hours=delay_hours),
            metadata={"retry_number": context.case.retry_count + 1, "delay_hours": delay_hours},
        )

    if category == FailureCategory.CARD_ISSUE:
        return Decision(
            action=RecoveryActionType.SEND_PAYMENT_UPDATE_LINK,
            next_status=CaseStatus.WAITING_FOR_CUSTOMER,
            reason="Card issue detected — sending payment-method-update link instead of blind retry.",
        )

    if category == FailureCategory.INSUFFICIENT_FUNDS:
        intervals = context.stopping_rule.retry_intervals_hours or [24]
        interval_index = min(context.case.retry_count, len(intervals) - 1)
        delay_hours = max(0, int(intervals[interval_index]))
        return Decision(
            action=RecoveryActionType.RETRY_LATER,
            next_status=CaseStatus.WAITING_FOR_RETRY,
            reason=f"Insufficient funds — scheduling bounded retry in {delay_hours}h.",
            execute_at=now + timedelta(hours=delay_hours),
            metadata={"retry_number": context.case.retry_count + 1, "delay_hours": delay_hours},
        )

    if category == FailureCategory.CUSTOMER_ACTION_NEEDED:
        return Decision(
            action=RecoveryActionType.NOTIFY_CUSTOMER,
            next_status=CaseStatus.WAITING_FOR_CUSTOMER,
            reason="Customer action needed (e.g. authentication) — notifying and waiting.",
        )

    # FailureCategory.UNKNOWN — deterministic rules and the LLM fallback
    # both failed to classify this. Don't guess an action; hand it to a
    # human via the exception/escalation queue (PRD F12).
    return Decision(
        action=RecoveryActionType.ESCALATE,
        next_status=CaseStatus.ESCALATED,
        reason="Unable to classify failure reason — escalating to human-handoff queue.",
    )
