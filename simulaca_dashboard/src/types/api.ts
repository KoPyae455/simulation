export interface AgentNeeds {
  hunger: number;
  thirst: number;
  fatigue: number;
  safety: number;
  comfort: number;
  social: number;
}

export interface Agent {
  id: string;
  name: string;
  needs: AgentNeeds;
  created_at: string;
  updated_at: string | null;
}

export interface CreateAgentInput {
  name: string;
  needs?: Partial<AgentNeeds>;
}

export interface HealthStatus {
  status: string;
  app_name: string;
  app_version: string;
  environment: string;
}

export interface SimulationStatus {
  current_tick: number;
  current_simulation_datetime: string;
  is_running: boolean;
}

export interface SimulationStepResult extends SimulationStatus {
  agents_updated: number;
}

export interface AgentDecisionLog {
  id: string;
  timestamp: string;
  agent_id: string;
  agent_name: string;
  action: string;
  reason: string;
  internal_state_snapshot: AgentNeeds;
}

export interface ApiErrorResponse {
  error_code?: string;
  message?: string;
}
