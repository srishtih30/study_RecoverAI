import { formatDateTime } from "../lib/format";
import type { AuditLogOut } from "../types/audit";

export default function AuditTimeline({ entries }: { entries: AuditLogOut[] }) {
  if (entries.length === 0) {
    return <p className="text-sm text-slate-500">No audit entries yet.</p>;
  }

  return (
    <ol className="space-y-3">
      {entries.map((entry) => (
        <li key={entry.id} className="border-l-2 border-slate-200 pl-4">
          <div className="flex items-baseline gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              {entry.event_type.replace(/_/g, " ")}
            </span>
            <span className="text-xs text-slate-400">by {entry.actor}</span>
            <span className="text-xs text-slate-400">· {formatDateTime(entry.created_at)}</span>
          </div>
          <p className="mt-0.5 text-sm text-slate-800">{entry.description}</p>
        </li>
      ))}
    </ol>
  );
}
