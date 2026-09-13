/**
 * Mirrors backend/app/domain/enums.py and backend/app/schemas/case.py.
 *
 * TODO(AG): keep these in sync by hand — if a backend enum or schema field
 * changes, update this file in the same change. There is no shared codegen
 * between the two yet (deliberately, for hackathon speed); consider adding
 * an OpenAPI-to-TS generation step if the schemas start drifting.
 */

export type CaseStatus =
  | "open"
  | "waiting_for_retry"
  | "waiting_for_customer"
  | "retrying"
  | "recovered"
  | "halted"
  | "escalated";

export type FailureCategory =
  | "retriable_technical"
  | "card_issue"
  | "insufficient_funds"
  | "customer_action_needed"
  | "unknown";

export type RecoveryActionType =
  | "retry_now"
  | "retry_later"
  | "send_payment_update_link"
  | "notify_customer"
  | "escalate"
  | "halt"
  | "no_action";

export type AttemptResult = "pending" | "success" | "failed" | "skipped";

export type EventSource = "razorpay_webhook" | "simulator";

export interface AttemptOut {
  id: string;
  case_id: string;
  action_type: RecoveryActionType;
  result: AttemptResult;
  scheduled_at: string | null;
  executed_at: string | null;
  razorpay_payment_id: string | null;
  reason: string | null;
  metadata_json: Record<string, unknown> | null;
  created_at: string;
}

export interface CaseSummary {
  id: string;
  subscription_id: string;
  customer_id: string | null;
  amount: number;
  currency: string;
  status: CaseStatus;
  failure_category: FailureCategory;
  retry_count: number;
  opted_out: boolean;
  source: EventSource;
  recovered_amount: number | null;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

import type { DecisionOut } from "./decision";

export interface CaseDetail extends CaseSummary {
  failure_reason_raw: string | null;
  attempts: AttemptOut[];
  last_decision: DecisionOut | null;
  last_decision_reason: string | null;
  next_action_at: string | null;
}

export interface CaseListResponse {
  items: CaseSummary[];
  total: number;
}
