"""RecoveryCase — the central aggregate: one case per at-risk subscription payment."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Enum as SAEnum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.enums import CaseStatus, EventSource, FailureCategory
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RecoveryCase(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "cases"

    subscription_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    customer_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    amount: Mapped[int] = mapped_column(Integer, nullable=False, comment="Amount at risk, in smallest currency unit (paise).")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="INR")

    status: Mapped[CaseStatus] = mapped_column(
        SAEnum(CaseStatus, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32),
        nullable=False,
        default=CaseStatus.OPEN,
        index=True,
    )
    failure_category: Mapped[FailureCategory] = mapped_column(
        SAEnum(FailureCategory, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32),
        nullable=False,
        default=FailureCategory.UNKNOWN,
    )
    failure_reason_raw: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    source: Mapped[EventSource] = mapped_column(
        SAEnum(EventSource, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32),
        nullable=False,
        default=EventSource.RAZORPAY_WEBHOOK,
        comment="Whether this case originated from a real Razorpay webhook or the simulator. Must never be blended silently.",
    )

    recovered_amount: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    attempts: Mapped[list["RecoveryAttempt"]] = relationship(
        "RecoveryAttempt", back_populates="case", cascade="all, delete-orphan", order_by="RecoveryAttempt.created_at"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(
        "AuditLog", back_populates="case", cascade="all, delete-orphan", order_by="AuditLog.created_at"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RecoveryCase id={self.id} status={self.status} subscription_id={self.subscription_id}>"


# NOTE: relationship() targets above ("RecoveryAttempt", "AuditLog") are resolved
# lazily by SQLAlchemy's mapper registry — this module deliberately does NOT
# import app.models.attempt / app.models.audit_log to avoid a circular import.
# app/models/__init__.py imports every model module once so the registry is
# fully populated before any query runs. Always import models via
# `from app import models` (or `from app.models import X`), never a single
# model file in isolation, or relationship resolution can fail.
