"""API response contracts for the audit trail. Mirror in frontend/src/types/audit.ts."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.domain.enums import AuditActor, AuditEventType


class AuditLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    case_id: Optional[str] = None
    event_type: AuditEventType
    actor: AuditActor
    description: str
    metadata_json: Optional[dict[str, Any]] = None
    created_at: datetime


class AuditHistoryResponse(BaseModel):
    case_id: str
    items: list[AuditLogOut]
