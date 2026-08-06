import type { AgentMemory } from "../types/api";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingState } from "./LoadingState";

interface MemoryPanelProps {
  memories: AgentMemory[];
  isLoading: boolean;
  error: string | null;
  onRefresh: () => Promise<void>;
  onDelete: (memoryId: string) => Promise<void>;
}

export function MemoryPanel({ memories, isLoading, error, onRefresh, onDelete }: MemoryPanelProps) {
  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4" aria-label="Agent memory panel">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-emerald-400">Memory Panel</p>
          <h2 className="text-lg font-semibold text-slate-100">Recent Memories</h2>
        </div>
        <button className="rounded border border-slate-600 px-3 py-2 text-sm text-slate-300 hover:bg-slate-800" type="button" onClick={() => void onRefresh()}>
          Refresh
        </button>
      </div>
      {error !== null && <div className="mt-4"><ErrorMessage message={error} /></div>}
      {isLoading && <div className="mt-4"><LoadingState label="memories" /></div>}
      <div className="mt-4 space-y-3">
        {!isLoading && memories.length === 0 && <p className="text-sm text-slate-500">No memories yet for the selected agent.</p>}
        {memories.map((memory) => (
          <article key={memory.id} className="rounded border border-slate-800 bg-slate-950/70 p-3 text-sm text-slate-300">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-medium text-slate-100">{memory.content}</p>
                <p className="mt-1 text-xs text-slate-500">{memory.memory_type} · {new Date(memory.created_at).toLocaleString()}</p>
              </div>
              <button className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-400 hover:bg-slate-800" type="button" onClick={() => void onDelete(memory.id)}>
                Delete
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
