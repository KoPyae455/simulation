import { useCallback, useEffect, useState } from "react";

import { listAgentEvents } from "../services/activityService";
import type { AgentActivityEvent } from "../types/api";

export function useAgentEvents(agentId: string | null) {
  const [events, setEvents] = useState<AgentActivityEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (agentId === null) {
      setEvents([]);
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      setEvents(await listAgentEvents(agentId));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load activity events.");
    } finally {
      setIsLoading(false);
    }
  }, [agentId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { events, isLoading, error, reload };
}