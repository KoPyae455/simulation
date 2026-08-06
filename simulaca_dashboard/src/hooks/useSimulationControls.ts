import { useCallback, useState } from "react";

import { startSimulation, stepSimulation, stopSimulation } from "../services/simulationService";
import type { SimulationStatus, SimulationStepResult } from "../types/api";

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unable to control the simulation.";
}

export function useSimulationControls(onStateChanged: () => Promise<void>) {
  const [status, setStatus] = useState<SimulationStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const step = useCallback(async (): Promise<SimulationStepResult> => {
    setIsLoading(true);
    setError(null);
    try {
      const result = await stepSimulation();
      setStatus(result);
      await onStateChanged();
      return result;
    } catch (requestError) {
      setError(errorMessage(requestError));
      throw requestError;
    } finally {
      setIsLoading(false);
    }
  }, [onStateChanged]);

  const start = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      setStatus(await startSimulation());
      await onStateChanged();
    } catch (requestError) {
      setError(errorMessage(requestError));
      throw requestError;
    } finally {
      setIsLoading(false);
    }
  }, [onStateChanged]);

  const stop = useCallback(async (): Promise<void> => {
    setIsLoading(true);
    setError(null);
    try {
      setStatus(await stopSimulation());
      await onStateChanged();
    } catch (requestError) {
      setError(errorMessage(requestError));
      throw requestError;
    } finally {
      setIsLoading(false);
    }
  }, [onStateChanged]);

  return { status, isLoading, error, step, start, stop };
}
