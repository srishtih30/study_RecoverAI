"""
Dashboard aggregate metrics (PRD F7 / Section 9).

NOTE: this loads all cases into memory and aggregates in Python rather than
with SQL aggregate queries. That's fine at hackathon/demo scale (dozens to a
few hundred cases from the batch simulator) but will not scale.
TODO(AG): replace with SQL-side aggregation (func.sum/func.count/GROUP BY)
before running this against a large case table.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.enums import CaseStatus, RecoveryActionType
from app.models.case import RecoveryCase
from app.services import stopping_rules


def compute_metrics(db: Session) -> dict[str, Any]:
    cases = db.query(RecoveryCase).all()

    total_cases = len(cases)
    cases_recovered = sum(1 for c in cases if c.status == CaseStatus.RECOVERED)
    cases_halted = sum(1 for c in cases if c.status == CaseStatus.HALTED)
    cases_escalated = sum(1 for c in cases if c.status == CaseStatus.ESCALATED)
    cases_open = total_cases - cases_recovered - cases_halted - cases_escalated

    total_recovered_amount = sum((c.recovered_amount or 0) for c in cases if c.status == CaseStatus.RECOVERED)
    total_at_risk_amount = sum(c.amount for c in cases if c.status != CaseStatus.RECOVERED)

    denominator = total_recovered_amount + total_at_risk_amount
    recovery_rate = (total_recovered_amount / denominator) if denominator > 0 else 0.0

    recovery_durations_seconds = [
        (c.resolved_at - c.created_at).total_seconds()
        for c in cases
        if c.status == CaseStatus.RECOVERED and c.resolved_at is not None
    ]
    average_time_to_recovery_seconds = (
        sum(recovery_durations_seconds) / len(recovery_durations_seconds) if recovery_durations_seconds else None
    )

    contact_actions = {RecoveryActionType.SEND_PAYMENT_UPDATE_LINK, RecoveryActionType.NOTIFY_CUSTOMER}
    compliance_violations = 0
    for case in cases:
        rule = stopping_rules.get_stopping_rule(db, case.failure_category)
        contact_count = sum(1 for attempt in case.attempts if attempt.action_type in contact_actions)
        if contact_count > rule.max_contacts:
            compliance_violations += 1

    return {
        "total_cases": total_cases,
        "cases_open": cases_open,
        "cases_recovered": cases_recovered,
        "cases_halted": cases_halted,
        "cases_escalated": cases_escalated,
        "total_at_risk_amount": total_at_risk_amount,
        "total_recovered_amount": total_recovered_amount,
        "recovery_rate": round(recovery_rate, 4),
        "average_time_to_recovery_seconds": average_time_to_recovery_seconds,
        # False-stop rate requires a counterfactual ("would one more attempt
        # have recovered?") that the event stream cannot establish honestly.
        "false_stop_rate": None,
        "compliance_violations": compliance_violations,
    }
