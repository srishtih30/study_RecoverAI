import { useState } from "react";
import { Link } from "react-router-dom";

import { runSimulation } from "../api/simulator";
import SimulatorControls from "../components/SimulatorControls";
import type { FailureCategory } from "../types/case";
import type { SimulationResponse } from "../types/simulation";

export default function SimulatorPage() {
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<SimulationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRun = async (count: number, failureCategory: FailureCategory | null) => {
    setIsRunning(true);
    setError(null);
    try {
      const response = await runSimulation({ count, failure_category: failureCategory });
      setResult(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Simulation failed.");
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-slate-900">Batch test harness</h1>
        <p className="text-sm text-slate-500">
          Generates synthetic subscription-payment failures (PRD F8), tagged{" "}
          <code className="rounded bg-slate-100 px-1">source=simulator</code> so they're never confused with real
          Razorpay test-mode traffic. They run through the exact same pipeline a real webhook does.
        </p>
      </div>

      <SimulatorControls onRun={handleRun} isRunning={isRunning} />

      {error && <p className="text-sm text-red-600">Error: {error}</p>}

      {result && (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
          <p>{result.message}</p>
          <Link to="/cases" className="mt-2 inline-block font-medium underline">
            View resulting cases →
          </Link>
        </div>
      )}
    </div>
  );
}
