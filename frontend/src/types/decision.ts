/** Mirrors backend/app/schemas/decision.py DecisionOut. Exposed via CaseDetail.last_decision. */

import type { CaseStatus, RecoveryActionType } from "./case";

export interface DecisionOut {
  action: RecoveryActionType;
  next_status: CaseStatus;
  reason: string;
  execute_at: string | null;
  metadata: Record<string, unknown>;
}
