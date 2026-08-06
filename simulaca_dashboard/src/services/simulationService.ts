import { apiRequest } from "./apiClient";
import type { SimulationStatus, SimulationStepResult } from "../types/api";

export function stepSimulation(): Promise<SimulationStepResult> {
  return apiRequest<SimulationStepResult>("/simulation/step", { method: "POST" });
}

export function startSimulation(): Promise<SimulationStatus> {
  return apiRequest<SimulationStatus>("/simulation/start", { method: "POST" });
}

export function stopSimulation(): Promise<SimulationStatus> {
  return apiRequest<SimulationStatus>("/simulation/stop", { method: "POST" });
}
