"""
Audit contract — the ONE write path for AuditLog rows.

Rule: no other module may construct `models.AuditLog(...)` directly. Every
automated decision or action that matters must go through `record_event`
here. Treat the audit trail as append-only from the application's point of
view — this module never updates or deletes an existing AuditLog row.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.domain.enums import AuditActor, AuditEventType
from app.models.audit_log import AuditLog


def record_event(
    db: Session,
    *,
    event_type: AuditEventType,
    actor: AuditActor,
    description: str,
    case_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    commit: bool = True,
) -> AuditLog:
    """Append one audit entry. Call this for every automated decision/action — see AGENTS.md."""
    entry = AuditLog(
        case_id=case_id,
        event_type=event_type,
        actor=actor,
        description=description,
        metadata_json=metadata or {},
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    else:
        db.flush()
    return entry


def get_case_audit(db: Session, case_id: str) -> list[AuditLog]:
    return (
        db.query(AuditLog)
        .filter(AuditLog.case_id == case_id)
        .order_by(AuditLog.created_at.asc())
        .all()
    )
