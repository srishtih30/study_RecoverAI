"""
AuditLog — append-only record of every automated decision/action (PRD F6).

Rule: application code must never construct an AuditLog row directly.
Always go through `app.services.audit_service.record_event(...)` — that is
the one write path (see AGENTS.md / ARCHITECTURE.md "Audit contract").
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AuditActor, AuditEventType
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.case import RecoveryCase


class AuditLog(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    case_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=True,
        comment="Nullable: some audit events (e.g. a duplicate webhook rejected pre-case-creation) aren't tied to a case yet.",
    )

    event_type: Mapped[AuditEventType] = mapped_column(
        SAEnum(AuditEventType, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32), nullable=False, index=True
    )
    actor: Mapped[AuditActor] = mapped_column(
        SAEnum(AuditActor, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32), nullable=False
    )
    description: Mapped[str] = mapped_column(String(1024), nullable=False)
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    case: Mapped[Optional["RecoveryCase"]] = relationship("RecoveryCase", back_populates="audit_logs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditLog id={self.id} case_id={self.case_id} event_type={self.event_type}>"
