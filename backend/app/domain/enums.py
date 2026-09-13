"""
Single source of truth for every domain enum in RecoverAI.

Rule: if you find yourself writing a literal string like "recovered" or
"card_issue" anywhere else in the codebase (SQLAlchemy models, Pydantic
schemas, service logic, Celery tasks, frontend TS types), stop — import the
enum from here instead (or mirror it deliberately in frontend/src/types with
a comment pointing back here). Duplicated-but-slightly-different string
constants are exactly how this kind of system silently breaks.
"""

from __future__ import annotations

from enum import Enum


class CaseStatus(str, Enum):
    """Lifecycle states of a RecoveryCase.

    Every case must terminate in RECOVERED, HALTED, or ESCALATED — no case
    may loop indefinitely (PRD Non-Functional Requirement: Boundedness).
    """

    OPEN = "open"
    WAITING_FOR_RETRY = "waiting_for_retry"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    RETRYING = "retrying"
    RECOVERED = "recovered"
    HALTED = "halted"
    ESCALATED = "escalated"

    @classmethod
    def terminal_statuses(cls) -> frozenset["CaseStatus"]:
        """Statuses from which the decision engine must not schedule further action."""
        return frozenset({cls.RECOVERED, cls.HALTED, cls.ESCALATED})


class FailureCategory(str, Enum):
    """Root-cause classification of a payment/subscription failure (PRD F2)."""

    RETRIABLE_TECHNICAL = "retriable_technical"
    CARD_ISSUE = "card_issue"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    CUSTOMER_ACTION_NEEDED = "customer_action_needed"
    UNKNOWN = "unknown"


class RecoveryActionType(str, Enum):
    """Actions the decision engine can select (PRD F3)."""

    RETRY_NOW = "retry_now"
    RETRY_LATER = "retry_later"
    SEND_PAYMENT_UPDATE_LINK = "send_payment_update_link"
    NOTIFY_CUSTOMER = "notify_customer"
    ESCALATE = "escalate"
    HALT = "halt"
    NO_ACTION = "no_action"


class AttemptResult(str, Enum):
    """Outcome of a single RecoveryAttempt."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class AuditEventType(str, Enum):
    """Lifecycle events recorded to the append-only audit log (PRD F6)."""

    WEBHOOK_RECEIVED = "webhook_received"
    WEBHOOK_SIGNATURE_INVALID = "webhook_signature_invalid"
    WEBHOOK_DUPLICATE_IGNORED = "webhook_duplicate_ignored"
    EVENT_NORMALIZED = "event_normalized"
    CASE_CREATED = "case_created"
    CASE_UPDATED = "case_updated"
    FAILURE_CLASSIFIED = "failure_classified"
    STOPPING_RULE_TRIGGERED = "stopping_rule_triggered"
    DECISION_MADE = "decision_made"
    ACTION_SCHEDULED = "action_scheduled"
    ACTION_EXECUTED = "action_executed"
    ACTION_FAILED = "action_failed"
    CASE_RECOVERED = "case_recovered"
    CASE_HALTED = "case_halted"
    CASE_ESCALATED = "case_escalated"
    SIMULATION_STARTED = "simulation_started"
    SIMULATION_EVENT_GENERATED = "simulation_event_generated"


class AuditActor(str, Enum):
    """Who/what caused an audited event. Required on every AuditLog row."""

    AGENT = "agent"       # the automated decision engine / executor
    SYSTEM = "system"      # infra-level (e.g. stopping-rule auto-halt, idempotency guard)
    HUMAN = "human"        # a human operator via the dashboard (future)
    SIMULATOR = "simulator"  # the batch test harness (PRD F8)


class EventSource(str, Enum):
    """
    Where a NormalizedEvent originated.

    Mandatory rule: simulator-generated outcomes must be clearly
    distinguishable from real Razorpay test-mode events (see AGENTS.md).
    Every NormalizedEvent, RecoveryCase, and RecoveryAttempt carries this so
    the dashboard and audit trail can label simulated data honestly instead
    of mixing it in with real Razorpay webhook traffic.
    """

    RAZORPAY_WEBHOOK = "razorpay_webhook"
    SIMULATOR = "simulator"


class NormalizedEventType(str, Enum):
    """
    Internal event-type vocabulary. The Razorpay integration layer maps raw
    provider event strings (e.g. "subscription.charged") onto this enum —
    downstream code (classifier, decision engine, case service) must only
    ever see these values, never raw Razorpay event names.
    """

    SUBSCRIPTION_PAYMENT_FAILED = "subscription_payment_failed"
    SUBSCRIPTION_CHARGED_SUCCESS = "subscription_charged_success"
    SUBSCRIPTION_PENDING = "subscription_pending"
    SUBSCRIPTION_HALTED = "subscription_halted"
    CHECKOUT_ABANDONED = "checkout_abandoned"  # stretch scope (PRD F9)
    UNKNOWN = "unknown"
