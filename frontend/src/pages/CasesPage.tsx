import { useEffect, useState } from "react";

import { getCases } from "../api/cases";
import CasesTable from "../components/CasesTable";
import type { CaseStatus, CaseSummary } from "../types/case";

const STATUS_FILTERS: (CaseStatus | "all")[] = [
  "all",
  "open",
  "waiting_for_retry",
  "waiting_for_customer",
  "retrying",
  "recovered",
  "halted",
  "escalated",
];

export default function CasesPage() {
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<CaseStatus | "all">("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    getCases(status === "all" ? {} : { status })
      .then((data) => {
        if (cancelled) return;
        setCases(data.items);
        setTotal(data.total);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load cases.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [status]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold text-slate-900">Cases ({total})</h1>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value as CaseStatus | "all")}
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
        >
          {STATUS_FILTERS.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All statuses" : s.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      {error && <p className="text-sm text-red-600">Error: {error}</p>}
      {loading ? <p className="text-sm text-slate-500">Loading…</p> : <CasesTable cases={cases} />}
    </div>
  );
}
