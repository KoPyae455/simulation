import type { SimulationStatus } from "../types/api";
import { ErrorMessage } from "./ErrorMessage";

interface SimulationControlsProps {
  status: SimulationStatus | null;
  isLoading: boolean;
  error: string | null;
  onStep: () => Promise<unknown>;
  onStart: () => Promise<void>;
  onStop: () => Promise<void>;
}

export function SimulationControls({ status, isLoading, error, onStep, onStart, onStop }: SimulationControlsProps) {
  const isRunning = status?.is_running ?? false;

  return (
    <section className="rounded-lg border border-sky-900 bg-slate-900 p-4" aria-label="Simulation control">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-sky-400">Simulation Control</p>
          <h2 className="text-lg font-semibold text-slate-100">Tick / Step Engine</h2>
        </div>
        <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${isRunning ? "bg-emerald-950 text-emerald-300" : "bg-slate-800 text-slate-400"}`}>
          {isRunning && <span className="inline-block size-2 animate-pulse rounded-full bg-emerald-400" />}
          {isRunning ? "AUTO-RUN ON" : "IDLE"}
        </span>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button className="rounded bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-500 disabled:cursor-not-allowed disabled:opacity-50" type="button" disabled={isLoading} onClick={() => void onStep()}>
          {isLoading ? "Working…" : "Next Step"}
        </button>
        <button className={`rounded px-4 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50 ${isRunning ? "bg-amber-700 hover:bg-amber-600" : "bg-emerald-700 hover:bg-emerald-600"}`} type="button" disabled={isLoading} onClick={() => void (isRunning ? onStop() : onStart())}>
          {isRunning ? "Stop Engine" : "Auto Run Engine"}
        </button>
        {status !== null && (
          <div className="text-sm text-slate-400">
            <p>Tick {status.current_tick} · {new Date(status.current_simulation_datetime).toLocaleTimeString()}</p>
            <p>Goal: <span className="text-slate-200">{status.current_goal ?? "idle"}</span> · Action: <span className="text-slate-200">{status.current_action ?? "idle"}</span></p>
          </div>
        )}
      </div>
      <p className="mt-3 text-xs text-slate-500">Auto-run advances simulation state on the backend every two seconds.</p>
      {error !== null && <div className="mt-3"><ErrorMessage message={error} /></div>}
    </section>
  );
}
