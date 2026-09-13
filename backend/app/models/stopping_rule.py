"""StoppingRuleConfig — bounded-retry configuration per failure category (PRD F5)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, Enum as SAEnum, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.enums import FailureCategory
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StoppingRuleConfig(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "stopping_rules_config"

    failure_category: Mapped[FailureCategory] = mapped_column(
        SAEnum(FailureCategory, values_callable=lambda enum: [e.value for e in enum], native_enum=False, length=32),
        unique=True,
        nullable=False,
        comment="One row per failure category. app/services/stopping_rules.py falls back to Settings.default_* if missing.",
    )
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    retry_intervals_hours: Mapped[list[Any]] = mapped_column(
        JSON, nullable=False, default=list, comment="e.g. [2, 24, 72] — hours to wait before each successive retry."
    )
    max_days_open: Mapped[int] = mapped_column(Integer, nullable=False, default=7)
    max_contacts: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    opt_out_respected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StoppingRuleConfig category={self.failure_category} max_retries={self.max_retries}>"
