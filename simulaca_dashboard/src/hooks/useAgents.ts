import { useCallback, useEffect, useState } from "react";

import { createAgent, deleteAgent, listAgents } from "../services/agentService";
import type { Agent, CreateAgentInput } from "../types/api";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "An unexpected API error occurred.";
}

export function useAgents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isMutating, setIsMutating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      setAgents(await listAgents());
    } catch (requestError) {
      setError(errorMessage(requestError));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const addAgent = useCallback(async (input: CreateAgentInput): Promise<Agent> => {
    setIsMutating(true);
    setError(null);

    try {
      const agent = await createAgent(input);
      setAgents((currentAgents) => [...currentAgents, agent]);
      return agent;
    } catch (requestError) {
      const message = errorMessage(requestError);
      setError(message);
      throw requestError;
    } finally {
      setIsMutating(false);
    }
  }, []);

  const removeAgent = useCallback(async (agentId: string): Promise<void> => {
    setIsMutating(true);
    setError(null);

    try {
      await deleteAgent(agentId);
      setAgents((currentAgents) => currentAgents.filter((agent) => agent.id !== agentId));
    } catch (requestError) {
      const message = errorMessage(requestError);
      setError(message);
      throw requestError;
    } finally {
      setIsMutating(false);
    }
  }, []);

  return { agents, isLoading, isMutating, error, reload, addAgent, removeAgent };
}
