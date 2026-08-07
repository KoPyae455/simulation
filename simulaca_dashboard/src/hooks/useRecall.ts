import { useCallback, useEffect, useState } from "react";

import { recallAgentMemories } from "../services/memoryService";
import type { Agent, AgentMemory } from "../types/api";

export function useRecall(agent: Agent | null) {
  const [memories, setMemories] = useState<AgentMemory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const computeGoal = (agentParam: Agent | null): string => {
    if (!agentParam) return "idle";
    if (agentParam.needs.thirst && agentParam.needs.thirst > 80) return "drink";
    if (agentParam.needs.hunger && agentParam.needs.hunger > 80) return "eat";
    if (agentParam.needs.fatigue && agentParam.needs.fatigue > 80) return "sleep";
    return "idle";
  };

  const reload = useCallback(async () => {
    const goal = computeGoal(agent);
    setIsLoading(true);
    setError(null);
    try {
      setMemories(await recallAgentMemories(agent?.id ?? null, goal));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to recall memories.");
    } finally {
      setIsLoading(false);
    }
  }, [agent]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { memories, isLoading, error, reload };
}
