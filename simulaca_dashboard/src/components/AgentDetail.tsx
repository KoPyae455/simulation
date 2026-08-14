import type { Agent, AgentActivityEvent } from "../types/api";
import { ActivityPanel } from "./ActivityPanel";
import { BrainPanel } from "./BrainPanel";
import { StateCard } from "./StateCard";

interface AgentDetailProps {
  agent: Agent | null;
  isDeleting: boolean;
  events: AgentActivityEvent[];
  eventsLoading: boolean;
  eventsError: string | null;
  onDelete: (agent: Agent) => Promise<void>;
}

const stateLabels = ["health", "hunger", "thirst", "fatigue", "social", "safety", "comfort"] as const;

export function AgentDetail({ agent, isDeleting, events, eventsLoading, eventsError, onDelete }: AgentDetailProps) {
  if (agent === null) {
    return <section className="rounded-lg border border-dashed border-slate-700 p-6 text-sm text-slate-400">Select an agent to inspect its internal state.</section>;
  }

  const stateValues: Record<(typeof stateLabels)[number], number | null> = {
    health: null,
    hunger: agent.needs.hunger,
    thirst: agent.needs.thirst,
    fatigue: agent.needs.fatigue,
    social: agent.needs.social,
    safety: agent.needs.safety,
    comfort: agent.needs.comfort,
  };

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-xl font-semibold text-slate-100">{agent.name}</h2>
          <p className="mt-1 break-all text-xs text-slate-400">{agent.id}</p>
        </div>
        <button className="rounded bg-red-700 px-3 py-2 text-sm font-medium text-white hover:bg-red-600 disabled:cursor-not-allowed disabled:opacity-50" type="button" disabled={isDeleting} onClick={() => void onDelete(agent)}>
          {isDeleting ? "Deleting…" : "Delete agent"}
        </button>
      </div>
      <div className="mt-6">
        <BrainPanel agent={agent} />
      </div>
      <dl className="mt-4 grid gap-2 text-sm text-slate-300 sm:grid-cols-2">
        <div><dt className="text-slate-500">Created</dt><dd>{new Date(agent.created_at).toLocaleString()}</dd></div>
        <div><dt className="text-slate-500">Updated</dt><dd>{agent.updated_at === null ? "Never" : new Date(agent.updated_at).toLocaleString()}</dd></div>
      </dl>
      <h3 className="mt-6 font-medium text-slate-200">Internal state</h3>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {stateLabels.map((label) => <StateCard key={label} label={label} value={stateValues[label]} />)}
      </div>
      <h3 className="mt-6 font-medium text-slate-200">Activity</h3>
      <ActivityPanel events={events} isLoading={eventsLoading} error={eventsError} />
    </section>
  );
}
