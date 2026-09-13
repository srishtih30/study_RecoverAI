"""RecoveryAttempt — one row per executed (or scheduled) recovery action."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import JSON, Enum as SAEnum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import AttemptResult, RecoveryActionType
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:  # pragma: no cover
    from app.models.case import RecoveryCase


class RecoveryAttempt(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "attempts"

    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)

    action_type: Mapped[RecoveryActionType] = mapped_column(
        SAEnum(RecoveryActionType, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32), nullable=False
    )
    result: Mapped[AttemptResult] = mapped_column(
        SAEnum(AttemptResult, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32),
        nullable=False,
        default=AttemptResult.PENDING,
    )

    scheduled_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    executed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    razorpay_payment_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="Decision.reason at the time this attempt was created.")
    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    case: Mapped["RecoveryCase"] = relationship("RecoveryCase", back_populates="attempts")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RecoveryAttempt id={self.id} case_id={self.case_id} action={self.action_type} result={self.result}>"
