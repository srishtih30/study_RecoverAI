import { apiFetch } from "./client";
import type { AuditHistoryResponse } from "../types/audit";
import type { CaseDetail, CaseListResponse, CaseStatus } from "../types/case";

export interface ListCasesParams {
  status?: CaseStatus;
  limit?: number;
  offset?: number;
}

export function getCases(params: ListCasesParams = {}): Promise<CaseListResponse> {
  const query = new URLSearchParams();
  if (params.status) query.set("status", params.status);
  if (params.limit !== undefined) query.set("limit", String(params.limit));
  if (params.offset !== undefined) query.set("offset", String(params.offset));
  const qs = query.toString();
  return apiFetch<CaseListResponse>(`/api/cases${qs ? `?${qs}` : ""}`);
}

export function getCase(caseId: string): Promise<CaseDetail> {
  return apiFetch<CaseDetail>(`/api/cases/${caseId}`);
}

export function getCaseAudit(caseId: string): Promise<AuditHistoryResponse> {
  return apiFetch<AuditHistoryResponse>(`/api/cases/${caseId}/audit`);
}
