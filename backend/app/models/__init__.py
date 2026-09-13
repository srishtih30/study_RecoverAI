"""
SQLAlchemy models — import from this package (`from app import models` or
`from app.models import RecoveryCase`), not from an individual model file in
isolation. Importing every model module here (once) ensures SQLAlchemy's
mapper registry can resolve the string-based `relationship()` references
used across case.py / attempt.py / audit_log.py before any query runs.

Source of truth for the actual columns/relationships: the individual files
in this package. Source of truth for the enums used as column types:
app/domain/enums.py.
"""

from app.models.base import Base
from app.models.case import RecoveryCase
from app.models.attempt import RecoveryAttempt
from app.models.audit_log import AuditLog
from app.models.processed_event import ProcessedWebhookEvent
from app.models.stopping_rule import StoppingRuleConfig

__all__ = [
    "Base",
    "RecoveryCase",
    "RecoveryAttempt",
    "AuditLog",
    "ProcessedWebhookEvent",
    "StoppingRuleConfig",
]
