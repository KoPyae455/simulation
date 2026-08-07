import type { Agent } from "../types/api";
import type { AgentMemory } from "../types/api";

interface RecallPanelProps {
  agent: Agent | null;
  memories: AgentMemory[];
}

export function RecallPanel({ agent, memories }: RecallPanelProps) {
  const selectedMemory = memories[0] ?? null;
  const goal = agent?.needs?.thirst && agent.needs.thirst > 80 ? "drink" : agent?.needs?.hunger && agent.needs.hunger > 80 ? "eat" : agent?.needs?.fatigue && agent.needs.fatigue > 80 ? "sleep" : "idle";

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4" aria-label="Memory recall panel">
      <div>
        <p className="text-sm font-medium text-sky-400">Recall Panel</p>
        <h2 className="text-lg font-semibold text-slate-100">Memory Recall</h2>
      </div>
      <div className="mt-4 space-y-3 text-sm text-slate-300">
        <div className="rounded border border-slate-800 bg-slate-950/70 p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Current Goal</p>
          <p className="mt-1 font-medium text-slate-100">{goal}</p>
        </div>
        <div className="rounded border border-slate-800 bg-slate-950/70 p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Recalled Memories</p>
          <ul className="mt-2 space-y-2">
            {memories.length === 0 && <li className="text-slate-500">No relevant memories yet.</li>}
            {memories.slice(0, 3).map((memory) => (
              <li key={memory.id} className="rounded border border-slate-800 bg-slate-900/70 p-2 text-xs">
                {memory.content}
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded border border-slate-800 bg-slate-950/70 p-3">
          <p className="text-xs uppercase tracking-wide text-slate-500">Selected Memory</p>
          <p className="mt-1 font-medium text-slate-100">{selectedMemory?.content ?? "None"}</p>
          <p className="mt-2 text-xs text-slate-500">Reason: {selectedMemory?.description ?? "No memory selected yet."}</p>
        </div>
      </div>
    </section>
  );
}
