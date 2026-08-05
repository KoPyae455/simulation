import { apiRequest } from "./apiClient";
import type { HealthStatus } from "../types/api";

export function getHealthStatus(): Promise<HealthStatus> {
  return apiRequest<HealthStatus>("/health");
}
