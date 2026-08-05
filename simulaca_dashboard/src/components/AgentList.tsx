import type { Agent } from "../types/api";
import { LoadingState } from "./LoadingState";

interface AgentListProps {
  agents: Agent[];
  selectedAgentId: string | null;
  isLoading: boolean;
  onSelect: (agentId: string) => void;
}

export function AgentList({ agents, selectedAgentId, isLoading, onSelect }: AgentListProps) {
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <h2 className="font-semibold text-slate-100">Agents ({agents.length})</h2>
      {isLoading && <LoadingState label="agents" />}
      {!isLoading && agents.length === 0 && <p className="py-4 text-sm text-slate-400">No agents have been created.</p>}
      <ul className="mt-3 space-y-2">
        {agents.map((agent) => (
          <li key={agent.id}>
            <button className={`w-full rounded-md border px-3 py-2 text-left text-sm ${selectedAgentId === agent.id ? "border-sky-400 bg-sky-950/50" : "border-slate-700 hover:bg-slate-800"}`} type="button" onClick={() => onSelect(agent.id)}>
              <span className="block font-medium text-slate-100">{agent.name}</span>
              <span className="block truncate text-xs text-slate-400">{agent.id}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
