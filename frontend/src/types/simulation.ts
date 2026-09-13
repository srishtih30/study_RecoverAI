/** Mirrors backend/app/schemas/simulation.py. */

import type { FailureCategory } from "./case";

export interface SimulationRequest {
  count: number;
  failure_category?: FailureCategory | null;
}

export interface SimulationResponse {
  requested: number;
  created_case_ids: string[];
  message: string;
}
