import { apiFetch } from "./client";
import type { MetricsResponse } from "../types/metrics";

export function getMetrics(): Promise<MetricsResponse> {
  return apiFetch<MetricsResponse>("/api/metrics");
}
