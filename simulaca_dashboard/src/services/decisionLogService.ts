import { apiRequest } from "./apiClient";
import type { AgentDecisionLog } from "../types/api";

export function listDecisionLogs(): Promise<AgentDecisionLog[]> {
  return apiRequest<AgentDecisionLog[]>("/logs?limit=200");
}

export function clearDecisionLogs(): Promise<void> {
  return apiRequest<void>("/logs", { method: "DELETE" });
}
