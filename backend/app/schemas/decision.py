"""
API-facing mirror of app.domain.decision.Decision.

Kept as a separate schema (rather than reusing the domain model directly in
API responses) so the domain contract and the wire contract can diverge
later without one change silently breaking the other — see AGENTS.md
"do not silently change API response shapes without updating the frontend".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

from app.domain.enums import CaseStatus, RecoveryActionType


class DecisionOut(BaseModel):
    action: RecoveryActionType
    next_status: CaseStatus
    reason: str
    execute_at: Optional[datetime] = None
    metadata: dict[str, Any] = {}
