import { apiRequest } from "./apiClient";
import type { AgentActivityEvent } from "../types/api";

export function listAgentEvents(agentId: string, limit = 200): Promise<AgentActivityEvent[]> {
  return apiRequest<AgentActivityEvent[]>(`/agents/${agentId}/events?limit=${limit}`);
}