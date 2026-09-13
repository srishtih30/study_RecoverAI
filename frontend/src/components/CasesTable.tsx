import { Link } from "react-router-dom";

import { formatAmount, formatDateTime } from "../lib/format";
import type { CaseSummary } from "../types/case";
import StatusBadge from "./StatusBadge";

export default function CasesTable({ cases }: { cases: CaseSummary[] }) {
  if (cases.length === 0) {
    return <div className="rounded-lg border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">No cases yet. Run a simulation to populate the feed.</div>;
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="min-w-full divide-y divide-slate-200 text-sm">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Subscription</th>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Amount</th>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Status</th>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Failure</th>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Source</th>
            <th className="px-4 py-2 text-left font-medium text-slate-500">Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {cases.map((c) => (
            <tr key={c.id} className="hover:bg-slate-50">
              <td className="px-4 py-2">
                <Link to={`/cases/${c.id}`} className="font-medium text-slate-900 hover:underline">
                  {c.subscription_id}
                </Link>
              </td>
              <td className="px-4 py-2 text-slate-700">{formatAmount(c.amount, c.currency)}</td>
              <td className="px-4 py-2">
                <StatusBadge status={c.status} />
              </td>
              <td className="px-4 py-2 text-slate-500">{c.failure_category.replace(/_/g, " ")}</td>
              <td className="px-4 py-2 text-slate-500">
                {c.source === "simulator" ? (
                  <span className="text-xs italic">simulated</span>
                ) : (
                  <span className="text-xs">razorpay</span>
                )}
              </td>
              <td className="px-4 py-2 text-slate-400">{formatDateTime(c.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
