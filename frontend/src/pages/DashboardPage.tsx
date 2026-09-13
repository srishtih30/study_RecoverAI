import { useEffect, useState } from "react";

import { getCases } from "../api/cases";
import { getMetrics } from "../api/metrics";
import CasesTable from "../components/CasesTable";
import MetricCard from "../components/MetricCard";
import { formatAmount } from "../lib/format";
import type { CaseSummary } from "../types/case";
import type { MetricsResponse } from "../types/metrics";

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [recentCases, setRecentCases] = useState<CaseSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    Promise.all([getMetrics(), getCases({ limit: 10 })])
      .then(([metricsData, casesData]) => {
        if (cancelled) return;
        setMetrics(metricsData);
        setRecentCases(casesData.items);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load dashboard data.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <p className="text-sm text-slate-500">Loading dashboard…</p>;
  if (error) return <p className="text-sm text-red-600">Error: {error}. Is the backend running at the configured API URL?</p>;
  if (!metrics) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Recovery dashboard</h1>
        <p className="text-sm text-slate-500">Live feed of at-risk cases and recovery outcomes (PRD F7).</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-7">
        <MetricCard label="₹ Recovered" value={formatAmount(metrics.total_recovered_amount)} />
        <MetricCard label="₹ At risk" value={formatAmount(metrics.total_at_risk_amount)} />
        <MetricCard label="Recovery rate" value={`${(metrics.recovery_rate * 100).toFixed(1)}%`} />
        <MetricCard label="Total cases" value={String(metrics.total_cases)} />
        <MetricCard
          label="Open / Recovered / Halted / Escalated"
          value={`${metrics.cases_open} / ${metrics.cases_recovered} / ${metrics.cases_halted} / ${metrics.cases_escalated}`}
        />
        <MetricCard
          label="Avg. recovery time"
          value={
            metrics.average_time_to_recovery_seconds == null
              ? "—"
              : `${Math.round(metrics.average_time_to_recovery_seconds / 60)} min`
          }
        />
        <MetricCard label="Compliance violations" value={String(metrics.compliance_violations)} />
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Recent cases</h2>
        <CasesTable cases={recentCases} />
      </div>
    </div>
  );
}
