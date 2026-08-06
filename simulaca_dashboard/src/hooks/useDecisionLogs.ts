import { useCallback, useEffect, useState } from "react";

import { clearDecisionLogs, listDecisionLogs } from "../services/decisionLogService";
import type { AgentDecisionLog } from "../types/api";

export function useDecisionLogs() {
  const [logs, setLogs] = useState<AgentDecisionLog[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isClearing, setIsClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      setLogs(await listDecisionLogs());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to load decision logs.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const clear = useCallback(async (): Promise<void> => {
    setIsClearing(true);
    setError(null);
    try {
      await clearDecisionLogs();
      setLogs([]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to clear decision logs.");
      throw requestError;
    } finally {
      setIsClearing(false);
    }
  }, []);

  return { logs, isLoading, isClearing, error, reload, clear };
}
