import { apiRequest } from "./apiClient";
import type { Agent, CreateAgentInput } from "../types/api";

export function listAgents(): Promise<Agent[]> {
  return apiRequest<Agent[]>("/agents?limit=200");
}

export function getAgent(agentId: string): Promise<Agent> {
  return apiRequest<Agent>(`/agents/${agentId}`);
}

export function createAgent(input: CreateAgentInput): Promise<Agent> {
  return apiRequest<Agent>("/agents", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function deleteAgent(agentId: string): Promise<void> {
  return apiRequest<void>(`/agents/${agentId}`, { method: "DELETE" });
}
