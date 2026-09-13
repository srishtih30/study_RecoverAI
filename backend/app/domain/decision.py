"""
Decision engine contract.

This module defines the TYPES for the decision contract only. The actual
decision logic lives in `app/services/decision_engine.py` — kept out of the
domain layer deliberately, since domain/ must stay free of business rules
that might change (only the shapes should be stable).

Conceptually the decision engine is a pure function:

    decide_next_action(context: DecisionContext) -> Decision

Mandatory rules (see AGENTS.md for the full list):
  * The decision engine must NOT call Razorpay.
  * The decision engine must NOT send notifications.
  * The decision engine must NOT schedule Celery jobs directly.
  * The decision engine must NOT write directly to the database.
  * It only inspects the `DecisionContext` it is given and returns a
    `Decision`. Everything with a side effect (persisting the case,
    scheduling a Celery task, calling Razorpay, writing audit entries)
    happens in the caller (`webhook_orchestrator` / `recovery_executor`)
    after the decision comes back.

This keeps the decision engine trivially unit-testable (pure input ->
output) and keeps Razorpay/DB/Celery concerns swappable without touching
recovery strategy logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.domain.enums import AttemptResult, CaseStatus, FailureCategory, RecoveryActionType


class AttemptSnapshot(BaseModel):
    """Read-only view of a single past RecoveryAttempt, for decision context."""

    action_type: RecoveryActionType
    result: AttemptResult
    scheduled_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None


class CaseSnapshot(BaseModel):
    """
    Read-only view of a RecoveryCase, decoupled from the SQLAlchemy model.

    The decision engine (and its tests) should never need to import
    `app.models` — it operates on this snapshot instead. `case_service` is
    responsible for building a `CaseSnapshot` from the ORM row before
    calling the decision engine.
    """

    id: str
    status: CaseStatus
    failure_category: FailureCategory
    amount: int
    currency: str = "INR"
    retry_count: int = 0
    opted_out: bool = False
    created_at: datetime
    last_attempt_at: Optional[datetime] = None


class StoppingRuleSnapshot(BaseModel):
    """Read-only view of the stopping-rule configuration applicable to a case."""

    max_retries: int
    retry_intervals_hours: list[int] = Field(
        default_factory=list, description="Ordered delay (in hours) before each successive retry attempt."
    )
    max_days_open: int
    max_contacts: int = Field(default=2, ge=0, description="Maximum customer-contact actions allowed for a case.")
    opt_out_respected: bool = True


class DecisionContext(BaseModel):
    """Everything `decide_next_action` is allowed to look at."""

    case: CaseSnapshot
    failure_category: FailureCategory
    history: list[AttemptSnapshot] = Field(default_factory=list)
    stopping_rule: StoppingRuleSnapshot
    stopping_rule_triggered: bool = Field(
        default=False, description="Set by stopping_rules.py before the decision engine runs; see services/stopping_rules.py."
    )
    stopping_rule_reason: Optional[str] = None


class Decision(BaseModel):
    """The decision engine's sole output."""

    action: RecoveryActionType
    next_status: CaseStatus
    reason: str = Field(..., description="Human-readable explanation, required for audit/explainability (PRD NFR).")
    execute_at: Optional[datetime] = Field(
        default=None, description="When the action should run, if delayed (e.g. retry_later). None means execute immediately."
    )
    metadata: dict[str, Any] = Field(default_factory=dict)
