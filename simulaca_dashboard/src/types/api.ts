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

export interface ApiErrorResponse {
  error_code?: string;
  message?: string;
}
