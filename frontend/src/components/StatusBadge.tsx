import type { CaseStatus } from "../types/case";

const STYLES: Record<CaseStatus, string> = {
  open: "bg-slate-100 text-slate-700",
  waiting_for_retry: "bg-amber-100 text-amber-800",
  waiting_for_customer: "bg-blue-100 text-blue-800",
  retrying: "bg-amber-100 text-amber-800",
  recovered: "bg-emerald-100 text-emerald-800",
  halted: "bg-red-100 text-red-800",
  escalated: "bg-purple-100 text-purple-800",
};

export default function StatusBadge({ status }: { status: CaseStatus }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {status.replace(/_/g, " ")}
    </span>
  );
}
