import { formatDateTime } from "../lib/format";
import type { CaseDetail } from "../types/case";
import StatusBadge from "./StatusBadge";

const ACTION_STYLES: Record<string, string> = {
  retry_now: "bg-blue-50 text-blue-700 border-blue-200",
  retry_later: "bg-indigo-50 text-indigo-700 border-indigo-200",
  send_payment_update_link: "bg-amber-50 text-amber-700 border-amber-200",
  notify_customer: "bg-violet-50 text-violet-700 border-violet-200",
  escalate: "bg-rose-50 text-rose-700 border-rose-200",
  halt: "bg-slate-100 text-slate-700 border-slate-300",
  no_action: "bg-gray-100 text-gray-700 border-gray-200",
};

export default function DecisionCard({ caseDetail }: { caseDetail: CaseDetail }) {
  const decision = caseDetail.last_decision;
  const reason = decision?.reason ?? caseDetail.last_decision_reason ?? "No decision recorded yet.";
  const nextActionAt = decision?.execute_at ?? caseDetail.next_action_at;
  const action = decision?.action;
  const metadata = decision?.metadata && Object.keys(decision.metadata).length > 0 ? decision.metadata : null;

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Current decision</h3>
        <StatusBadge status={caseDetail.status} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {action && (
          <span
            className={`inline-flex items-center rounded border px-2.5 py-0.5 text-xs font-semibold capitalize ${
              ACTION_STYLES[action] ?? "bg-slate-100 text-slate-700 border-slate-200"
            }`}
          >
            Action: {action.replace(/_/g, " ")}
          </span>
        )}
        {nextActionAt ? (
          <span className="inline-flex items-center rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
            ⏰ Next action: {formatDateTime(nextActionAt)}
          </span>
        ) : action ? (
          <span className="inline-flex items-center rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">
            Immediate execution
          </span>
        ) : null}
      </div>

      <p className="mt-2.5 text-sm text-slate-700 leading-relaxed">{reason}</p>

      {metadata && (
        <div className="mt-3 border-t border-slate-100 pt-2.5">
          <span className="text-xs font-medium text-slate-500">Decision details:</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {Object.entries(metadata).map(([key, value]) => (
              <span
                key={key}
                className="inline-flex items-center rounded bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 border border-slate-200"
              >
                <span className="font-medium text-slate-500 mr-1">{key.replace(/_/g, " ")}:</span>
                {typeof value === "object" && value !== null ? JSON.stringify(value) : String(value)}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
