import { useState } from "react";

import type { FailureCategory } from "../types/case";

const FAILURE_CATEGORIES: FailureCategory[] = [
  "retriable_technical",
  "card_issue",
  "insufficient_funds",
  "customer_action_needed",
  "unknown",
];

export default function SimulatorControls({
  onRun,
  isRunning,
}: {
  onRun: (count: number, failureCategory: FailureCategory | null) => void;
  isRunning: boolean;
}) {
  const [count, setCount] = useState(10);
  const [failureCategory, setFailureCategory] = useState<FailureCategory | "">("");

  return (
    <form
      className="flex flex-wrap items-end gap-3 rounded-lg border border-slate-200 bg-white p-4"
      onSubmit={(e) => {
        e.preventDefault();
        onRun(count, failureCategory === "" ? null : failureCategory);
      }}
    >
      <label className="flex flex-col text-sm">
        <span className="mb-1 text-slate-600">Number of events</span>
        <input
          type="number"
          min={1}
          max={200}
          value={count}
          onChange={(e) => setCount(Number(e.target.value))}
          className="w-28 rounded-md border border-slate-300 px-2 py-1"
        />
      </label>

      <label className="flex flex-col text-sm">
        <span className="mb-1 text-slate-600">Failure category (optional)</span>
        <select
          value={failureCategory}
          onChange={(e) => setFailureCategory(e.target.value as FailureCategory | "")}
          className="w-56 rounded-md border border-slate-300 px-2 py-1"
        >
          <option value="">Realistic mix</option>
          {FAILURE_CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {c.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </label>

      <button
        type="submit"
        disabled={isRunning}
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50"
      >
        {isRunning ? "Running…" : "Run batch simulation"}
      </button>
    </form>
  );
}
