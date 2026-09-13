/** Mirrors backend/app/schemas/metrics.py. */

export interface MetricsResponse {
  total_cases: number;
  cases_open: number;
  cases_recovered: number;
  cases_halted: number;
  cases_escalated: number;
  total_at_risk_amount: number;
  total_recovered_amount: number;
  recovery_rate: number;
  average_time_to_recovery_seconds: number | null;
  false_stop_rate: number | null;
  compliance_violations: number;
}
