/** Mirrors backend/app/schemas/audit.py + app/domain/enums.py (AuditActor, AuditEventType). */

export type AuditActor = "agent" | "system" | "human" | "simulator";

export type AuditEventType =
  | "webhook_received"
  | "webhook_signature_invalid"
  | "webhook_duplicate_ignored"
  | "event_normalized"
  | "case_created"
  | "case_updated"
  | "failure_classified"
  | "stopping_rule_triggered"
  | "decision_made"
  | "action_scheduled"
  | "action_executed"
  | "action_failed"
  | "case_recovered"
  | "case_halted"
  | "case_escalated"
  | "simulation_started"
  | "simulation_event_generated";

export interface AuditLogOut {
  id: string;
  case_id: string | null;
  event_type: AuditEventType;
  actor: AuditActor;
  description: string;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditHistoryResponse {
  case_id: string;
  items: AuditLogOut[];
}
