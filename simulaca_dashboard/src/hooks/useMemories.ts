import { useCallback, useEffect, useState } from "react";

import { deleteAgentMemory, listAgentMemories } from "../services/memoryService";
import type { AgentMemory } from "../types/api";

export function useMemories(agentId: string | null) {
  const [memories, setMemories] = useState<AgentMemory[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (agentId === null) {
      setMemories([]);
      return;
    }

    setIsLoading(true);
    setError(null);
    try {
      setMemories(await listAgentMemories(agentId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load memories.");
    } finally {
      setIsLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const deleteMemory = useCallback(async (memoryId: string) => {
    setError(null);
    try {
      await deleteAgentMemory(memoryId);
      setMemories((current) => current.filter((memory) => memory.id !== memoryId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to delete memory.");
      throw requestError;
    }
  }, []);

  return { memories, isLoading, error, reload, deleteMemory };
}
