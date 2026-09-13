import { apiFetch } from "./client";
import type { SimulationRequest, SimulationResponse } from "../types/simulation";

export function runSimulation(payload: SimulationRequest): Promise<SimulationResponse> {
  return apiFetch<SimulationResponse>("/api/simulator/run", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
