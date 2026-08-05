import { useCallback, useEffect, useState } from "react";

import { getHealthStatus } from "../services/healthService";
import type { HealthStatus } from "../types/api";

export function useApiStatus() {
  const [status, setStatus] = useState<HealthStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      setStatus(await getHealthStatus());
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to reach the API.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { status, isLoading, error, reload };
}
