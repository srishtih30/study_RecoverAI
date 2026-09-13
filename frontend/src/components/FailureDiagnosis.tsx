import type { CaseDetail } from "../types/case";

export default function FailureDiagnosis({ caseDetail }: { caseDetail: CaseDetail }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-slate-900">Failure diagnosis</h3>
      <dl className="mt-2 space-y-1 text-sm">
        <div className="flex justify-between">
          <dt className="text-slate-500">Category</dt>
          <dd className="font-medium text-slate-900">{caseDetail.failure_category.replace(/_/g, " ")}</dd>
        </div>
        <div className="flex justify-between gap-4">
          <dt className="text-slate-500">Raw reason</dt>
          <dd className="text-right text-slate-700">{caseDetail.failure_reason_raw ?? "—"}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-slate-500">Retry count</dt>
          <dd className="text-slate-700">{caseDetail.retry_count}</dd>
        </div>
      </dl>
    </div>
  );
}
