import { useEffect, useMemo, useState } from "react";

import { AgentCreateForm } from "./components/AgentCreateForm";
import { AgentDetail } from "./components/AgentDetail";
import { AgentList } from "./components/AgentList";
import { ApiStatus } from "./components/ApiStatus";
import { ErrorMessage } from "./components/ErrorMessage";
import { DecisionLogsPanel } from "./components/DecisionLogsPanel";
import { SimulationControls } from "./components/SimulationControls";
import { useAgents } from "./hooks/useAgents";
import { useApiStatus } from "./hooks/useApiStatus";
import { useDecisionLogs } from "./hooks/useDecisionLogs";
import { useSimulationControls } from "./hooks/useSimulationControls";
import type { Agent } from "./types/api";

export function App() {
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const { agents, isLoading, isMutating, error, reload, addAgent, removeAgent } = useAgents();
  const apiStatus = useApiStatus();
  const decisionLogs = useDecisionLogs();
  const simulation = useSimulationControls(async () => {
    await Promise.all([reload(), decisionLogs.reload()]);
  });
  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedAgentId) ?? null,
    [agents, selectedAgentId],
  );

  useEffect(() => {
    if (!simulation.status?.is_running) {
      return undefined;
    }

    const interval = window.setInterval(() => {
      void Promise.all([reload(), decisionLogs.reload()]);
    }, 2_000);
    return () => window.clearInterval(interval);
  }, [decisionLogs.reload, reload, simulation.status?.is_running]);

  async function handleCreate(name: string): Promise<void> {
    const agent = await addAgent({ name });
    setSelectedAgentId(agent.id);
  }

  async function handleDelete(agent: Agent): Promise<void> {
    if (!window.confirm(`Delete ${agent.name}?`)) {
      return;
    }

    await removeAgent(agent.id);
    if (selectedAgentId === agent.id) {
      setSelectedAgentId(null);
    }
  }

  return (
    <main className="mx-auto min-h-screen max-w-7xl p-4 sm:p-6">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-sky-400">Developer tools</p>
          <h1 className="text-3xl font-bold tracking-tight text-slate-100">Simulaca Dashboard</h1>
        </div>
        <button className="rounded bg-slate-700 px-3 py-2 text-sm hover:bg-slate-600" type="button" onClick={() => void reload()} disabled={isLoading}>
          Refresh agents
        </button>
      </header>

      <ApiStatus {...apiStatus} onRefresh={() => void apiStatus.reload()} />
      <div className="mt-6">
        <SimulationControls
          status={simulation.status}
          isLoading={simulation.isLoading}
          error={simulation.error}
          onStep={simulation.step}
          onStart={simulation.start}
          onStop={simulation.stop}
        />
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="space-y-6">
          <AgentCreateForm isSubmitting={isMutating} onCreate={handleCreate} />
          {error !== null && <ErrorMessage message={error} />}
          <AgentList agents={agents} selectedAgentId={selectedAgentId} isLoading={isLoading} onSelect={setSelectedAgentId} />
        </aside>
        <AgentDetail agent={selectedAgent} isDeleting={isMutating} onDelete={handleDelete} />
      </div>
      <div className="mt-6">
        <DecisionLogsPanel
          logs={decisionLogs.logs}
          isLoading={decisionLogs.isLoading}
          isClearing={decisionLogs.isClearing}
          error={decisionLogs.error}
          onClear={decisionLogs.clear}
        />
      </div>
    </main>
  );
}
