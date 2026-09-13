import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getCase, getCaseAudit } from "../api/cases";
import AuditTimeline from "../components/AuditTimeline";
import DecisionCard from "../components/DecisionCard";
import FailureDiagnosis from "../components/FailureDiagnosis";
import { formatAmount, formatDateTime } from "../lib/format";
import type { AuditLogOut } from "../types/audit";
import type { CaseDetail } from "../types/case";

export default function CaseDetailPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const [caseDetail, setCaseDetail] = useState<CaseDetail | null>(null);
  const [auditEntries, setAuditEntries] = useState<AuditLogOut[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setLoading(true);

    Promise.all([getCase(caseId), getCaseAudit(caseId)])
      .then(([caseData, auditData]) => {
        if (cancelled) return;
        setCaseDetail(caseData);
        setAuditEntries(auditData.items);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Failed to load case.");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (loading) return <p className="text-sm text-slate-500">Loading case…</p>;
  if (error) return <p className="text-sm text-red-600">Error: {error}</p>;
  if (!caseDetail) return <p className="text-sm text-slate-500">Case not found.</p>;

  return (
    <div className="space-y-6">
      <div>
        <Link to="/cases" className="text-sm text-slate-500 hover:underline">
          ← Back to cases
        </Link>
        <h1 className="mt-1 text-xl font-semibold text-slate-900">{caseDetail.subscription_id}</h1>
        <p className="text-sm text-slate-500">
          {formatAmount(caseDetail.amount, caseDetail.currency)} · {caseDetail.source === "simulator" ? "simulated" : "razorpay"}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <FailureDiagnosis caseDetail={caseDetail} />
        <DecisionCard caseDetail={caseDetail} />
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Attempt history</h2>
        {caseDetail.attempts.length === 0 ? (
          <p className="text-sm text-slate-500">No attempts yet.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="px-4 py-2 text-left font-medium text-slate-500">Action</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-500">Result</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-500">Scheduled</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-500">Executed</th>
                  <th className="px-4 py-2 text-left font-medium text-slate-500">Reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {caseDetail.attempts.map((a) => (
                  <tr key={a.id}>
                    <td className="px-4 py-2">{a.action_type.replace(/_/g, " ")}</td>
                    <td className="px-4 py-2">{a.result}</td>
                    <td className="px-4 py-2 text-slate-400">{formatDateTime(a.scheduled_at)}</td>
                    <td className="px-4 py-2 text-slate-400">{formatDateTime(a.executed_at)}</td>
                    <td className="px-4 py-2 text-slate-600">{a.reason ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">Audit trail</h2>
        <AuditTimeline entries={auditEntries} />
      </div>
    </div>
  );
}
