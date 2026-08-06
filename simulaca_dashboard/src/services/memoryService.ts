import { apiRequest } from "./apiClient";
import type { AgentMemory } from "../types/api";

export function listAgentMemories(agentId: string | null): Promise<AgentMemory[]> {
  if (agentId === null) {
    return Promise.resolve([]);
  }
  return apiRequest<AgentMemory[]>(`/agents/${agentId}/memories`);
}

export function createAgentMemory(agentId: string, content: string, memoryType: string): Promise<AgentMemory> {
  return apiRequest<AgentMemory>(`/agents/${agentId}/memories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ memory_type: memoryType, content }),
  });
}

export function deleteAgentMemory(memoryId: string): Promise<void> {
  return apiRequest<void>(`/memories/${memoryId}`, { method: "DELETE" });
}
