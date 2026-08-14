import { useEffect, useRef } from "react";

import type { AgentActivityEvent } from "../types/api";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingState } from "./LoadingState";

interface ActivityPanelProps {
  events: AgentActivityEvent[];
  isLoading: boolean;
  error: string | null;
}

const eventStyle: Record<string, { label: string; badge: string; text: string }> = {
  need_changed: { label: "NEED", badge: "border-amber-500/40 text-amber-300", text: "text-amber-200" },
  goal_changed: { label: "GOAL", badge: "border-sky-500/40 text-sky-300", text: "text-sky-200" },
  decision: { label: "DECISION", badge: "border-violet-500/40 text-violet-300", text: "text-violet-200" },
  plan_created: { label: "PLAN", badge: "border-cyan-500/40 text-cyan-300", text: "text-cyan-200" },
  action_started: { label: "ACTION", badge: "border-emerald-500/40 text-emerald-300", text: "text-emerald-200" },
  action_completed: { label: "ACTION", badge: "border-emerald-500/40 text-emerald-300", text: "text-emerald-200" },
  state_changed: { label: "STATE", badge: "border-orange-500/40 text-orange-300", text: "text-orange-200" },
  memory_created: { label: "MEMORY", badge: "border-pink-500/40 text-pink-300", text: "text-pink-200" },
  reflection: { label: "REFLECT", badge: "border-indigo-500/40 text-indigo-300", text: "text-indigo-200" },
  knowledge: { label: "KNOWLEDGE", badge: "border-teal-500/40 text-teal-300", text: "text-teal-200" },
  error: { label: "ERROR", badge: "border-red-500/40 text-red-300", text: "text-red-200" },
  fallback: { label: "FALLBACK", badge: "border-yellow-500/40 text-yellow-300", text: "text-yellow-200" },
};

const fallbackStyle = { label: "EVENT", badge: "border-slate-600 text-slate-300", text: "text-slate-200" };

function styleFor(eventType: string) {
  return eventStyle[eventType] ?? fallbackStyle;
}

function messageLines(message: string): string[] {
  // Plan step summaries are joined with "; " on the backend.
  return message.includes("; ") ? message.split("; ") : [message];
}

export function ActivityPanel({ events, isLoading, error }: ActivityPanelProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const node = scrollRef.current;
    if (node !== null) {
      node.scrollTop = node.scrollHeight;
    }
  }, [events]);

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4" aria-label="Agent activity timeline">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-sky-400">Activity</p>
          <h2 className="text-lg font-semibold text-slate-100">Agent Timeline</h2>
        </div>
        <span className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400">{events.length} events</span>
      </div>
      {error !== null && <div className="mt-4"><ErrorMessage message={error} /></div>}
      {isLoading && <div className="mt-4"><LoadingState label="activity events" /></div>}
      <div ref={scrollRef} className="mt-4 max-h-96 min-h-40 space-y-2 overflow-y-auto pr-1 text-sm">
        {!isLoading && events.length === 0 && <p className="text-slate-500">No activity yet. Advance the simulation to watch the agent behave.</p>}
        {events.map((event) => {
          const style = styleFor(event.event_type);
          return (
            <div
              key={event.id}
              className="rounded border border-slate-800 bg-slate-950/60 px-3 py-2 font-mono text-xs"
            >
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="text-slate-500">{new Date(event.timestamp).toLocaleTimeString()}</span>
                <span className={`rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide ${style.badge}`}>
                  {style.label}
                </span>
                <span className="text-slate-600">tick {event.tick}</span>
              </div>
              {messageLines(event.message).map((line, index) => (
                <p key={`${event.id}-${index}`} className={`mt-1 break-words ${style.text}`}>{line}</p>
              ))}
            </div>
          );
        })}
      </div>
    </section>
  );
}