import { apiRequest } from "./apiClient";

export interface BrainStatusResponse {
  planner: string;
  model: string | null;
  provider: string | null;
  fallback_to_rules: boolean;
  llm_available: boolean | null;
  decisions: BrainDecisionSummary[];
  latest_llm_request: BrainLlmRequest | null;
}

export interface BrainDecisionSummary {
  agent_id: string;
  agent_name: string;
  tick: number;
  timestamp: string;
  planner: string;
  goal: string;
  status: string;
  plan: BrainPlan | null;
  executed_action: string | null;
  latency_ms: number | null;
  fallback_reason: string | null;
  reasoning_summary: string | null;
  model: string | null;
}

export interface BrainPlan {
  plan_id: string;
  goal: string;
  reasoning_summary: string;
  steps: BrainPlanStep[];
}

export interface BrainPlanStep {
  action: string;
  target: string | null;
  parameters: Record<string, unknown>;
}

export interface BrainLlmRequest {
  agent_id: string;
  tick: number;
  model: string;
  planner_type: string;
  latency_ms: number | null;
  status: string;
  error_type: string | null;
  plan_id: string | null;
  timestamp: string;
}

export interface AgentDecisionResponse {
  details: BrainDecisionSummary;
}

export interface AgentPlanResponse {
  plan: BrainPlan | null;
}

export function getBrainStatus(): Promise<BrainStatusResponse> {
  return apiRequest<BrainStatusResponse>("/brain/status");
}

export function getAgentDecision(agentId: string): Promise<AgentDecisionResponse> {
  return apiRequest<AgentDecisionResponse>(`/agents/${agentId}/decision`);
}

export function getAgentPlan(agentId: string): Promise<AgentPlanResponse> {
  return apiRequest<AgentPlanResponse>(`/agents/${agentId}/plan`);
}