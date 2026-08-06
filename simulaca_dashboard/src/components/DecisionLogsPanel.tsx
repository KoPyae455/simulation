import { useEffect, useRef, useState } from "react";

import type { AgentDecisionLog } from "../types/api";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingState } from "./LoadingState";

interface DecisionLogsPanelProps {
  logs: AgentDecisionLog[];
  isLoading: boolean;
  isClearing: boolean;
  error: string | null;
  onClear: () => Promise<void>;
}

function entryColor(log: AgentDecisionLog): string {
  return log.action === "WAIT" ? "text-emerald-300" : "text-amber-300";
}

export function DecisionLogsPanel({ logs, isLoading, isClearing, error, onClear }: DecisionLogsPanelProps) {
  const [autoScroll, setAutoScroll] = useState(true);
  const terminalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (autoScroll) {
      terminalRef.current?.scrollTo({ top: terminalRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [autoScroll, logs]);

  return (
    <section className="rounded-lg border border-slate-700 bg-[#090d14] font-mono shadow-inner shadow-black/40" aria-label="Agent decision logs">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700 px-4 py-3">
        <div>
          <p className="text-xs text-emerald-400">simulaca@brain:~$ tail -f agent-decisions.log</p>
          <h2 className="mt-1 font-sans text-lg font-semibold text-slate-100">Agent Decision Logs</h2>
        </div>
        <div className="flex items-center gap-3 text-xs">
          <label className="flex cursor-pointer items-center gap-2 text-slate-300">
            <input type="checkbox" checked={autoScroll} onChange={(event) => setAutoScroll(event.target.checked)} />
            Auto-scroll
          </label>
          <button className="rounded border border-slate-600 px-2 py-1 text-slate-300 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50" type="button" disabled={isClearing} onClick={() => void onClear()}>
            {isClearing ? "Clearing…" : "Clear Logs"}
          </button>
        </div>
      </header>
      {error !== null && <div className="p-4"><ErrorMessage message={error} /></div>}
      {isLoading && <div className="px-4"><LoadingState label="decision logs" /></div>}
      <div ref={terminalRef} className="max-h-80 min-h-48 overflow-y-auto p-4 text-xs leading-6 text-slate-300">
        {!isLoading && logs.length === 0 && <p className="text-slate-500">No decision logs yet. Advance the simulation to create entries.</p>}
        {logs.map((log) => (
          <p key={log.id} className={`break-words ${entryColor(log)}`}>
            <span className="text-slate-500">[{new Date(log.timestamp).toLocaleTimeString()}]</span>{" "}
            <span className="text-sky-300">[{log.agent_name}]</span>{" "}
            Action: <strong>{log.action}</strong> | Reason: {log.reason}
          </p>
        ))}
      </div>
    </section>
  );
}
