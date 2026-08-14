import { useEffect, useMemo, useState } from "react";

import type { Agent } from "../types/api";
import { ErrorMessage } from "./ErrorMessage";
import { LoadingState } from "./LoadingState";
import { getAgentDecision, getAgentPlan, getBrainStatus, type BrainDecisionSummary, type BrainPlan, type BrainStatusResponse } from "../services/brainService";

interface BrainPanelProps {
  agent: Agent | null;
}

function formatNullableValue(value: string | number | boolean | null): string {
  if (value === null) {
    return "—";
  }
  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }
  return String(value);
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-slate-400">{label}</dt>
      <dd className="break-words text-slate-100">{value}</dd>
    </div>
  );
}

function PlanCard({ plan }: { plan: BrainPlan | null }) {
  if (plan === null) {
    return <p className="text-sm text-slate-400">No validated plan is available for this agent yet.</p>;
  }

  return (
    <div className="space-y-3 rounded-md border border-slate-700 bg-slate-950/50 p-3">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">Plan</p>
        <h4 className="mt-1 font-medium text-slate-100">{plan.goal}</h4>
        {plan.reasoning_summary.length > 0 && <p className="mt-1 text-sm text-slate-400">{plan.reasoning_summary}</p>}
      </div>
      <ol className="space-y-2 text-sm">
        {plan.steps.length === 0 && <li className="text-slate-500">No steps were generated.</li>}
        {plan.steps.map((step, index) => (
          <li key={`${plan.plan_id}-${index}`} className="rounded border border-slate-800 bg-slate-900/70 p-2 text-slate-200">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded bg-sky-950/80 px-2 py-0.5 font-mono text-xs text-sky-300">{step.action}</span>
              <span className="text-slate-400">target:</span>
              <span className="font-mono text-slate-200">{step.target ?? "—"}</span>
            </div>
            {Object.keys(step.parameters).length > 0 && (
              <pre className="mt-2 overflow-x-auto rounded bg-black/30 p-2 text-xs text-slate-300">
                {JSON.stringify(step.parameters, null, 2)}
              </pre>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

function DecisionSummaryCard({ decision }: { decision: BrainDecisionSummary | null }) {
  if (decision === null) {
    return <p className="text-sm text-slate-400">No decision metadata has been recorded for this agent yet.</p>;
  }

  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-2">
      <DetailRow label="Planner" value={decision.planner} />
      <DetailRow label="Status" value={decision.status} />
      <DetailRow label="Goal" value={decision.goal} />
      <DetailRow label="Executed action" value={formatNullableValue(decision.executed_action)} />
      <DetailRow label="Model" value={formatNullableValue(decision.model)} />
      <DetailRow label="Latency (ms)" value={formatNullableValue(decision.latency_ms)} />
      <DetailRow label="Fallback reason" value={formatNullableValue(decision.fallback_reason)} />
      <DetailRow label="Reasoning summary" value={formatNullableValue(decision.reasoning_summary)} />
    </dl>
  );
}

export function BrainPanel({ agent }: BrainPanelProps) {
  const [brainStatus, setBrainStatus] = useState<BrainStatusResponse | null>(null);
  const [decision, setDecision] = useState<BrainDecisionSummary | null>(null);
  const [plan, setPlan] = useState<BrainPlan | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const agentId = agent?.id ?? null;

  useEffect(() => {
    let isActive = true;

    async function loadBrainData(): Promise<void> {
      if (agentId === null) {
        setBrainStatus(null);
        setDecision(null);
        setPlan(null);
        setError(null);
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const [status, decisionResponse, planResponse] = await Promise.allSettled([
          getBrainStatus(),
          getAgentDecision(agentId),
          getAgentPlan(agentId),
        ]);

        if (!isActive) {
          return;
        }

        if (status.status === "fulfilled") {
          setBrainStatus(status.value);
        } else {
          setBrainStatus(null);
          throw status.reason;
        }

        if (decisionResponse.status === "fulfilled") {
          setDecision(decisionResponse.value.details);
        } else {
          setDecision(null);
        }

        if (planResponse.status === "fulfilled") {
          setPlan(planResponse.value.plan);
        } else {
          setPlan(null);
        }
      } catch (requestError) {
        if (!isActive) {
          return;
        }
        setError(requestError instanceof Error ? requestError.message : "Unable to load brain data.");
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    }

    void loadBrainData();

    return () => {
      isActive = false;
    };
  }, [agentId]);

  const statusSummary = useMemo(() => {
    if (brainStatus === null) {
      return null;
    }

    return [
      { label: "Planner", value: brainStatus.planner },
      { label: "Provider", value: formatNullableValue(brainStatus.provider) },
      { label: "Model", value: formatNullableValue(brainStatus.model) },
      { label: "LLM available", value: formatNullableValue(brainStatus.llm_available) },
      { label: "Rule fallback", value: formatNullableValue(brainStatus.fallback_to_rules) },
    ];
  }, [brainStatus]);

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900 p-4" aria-label="Brain panel">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-[0.2em] text-sky-400">Brain</p>
          <h3 className="mt-1 text-lg font-semibold text-slate-100">Planner overview</h3>
        </div>
        {agent === null && <span className="rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400">Select an agent</span>}
      </div>

      {isLoading && <LoadingState label="brain data" />}
      {error !== null && <div className="mt-3"><ErrorMessage message={error} /></div>}

      {brainStatus !== null && (
        <dl className="mt-4 grid gap-3 rounded-md border border-slate-800 bg-slate-950/40 p-3 text-sm sm:grid-cols-2 xl:grid-cols-3">
          {statusSummary?.map((item) => (
            <div key={item.label}>
              <dt className="text-slate-500">{item.label}</dt>
              <dd className="break-words text-slate-100">{item.value}</dd>
            </div>
          ))}
          <div className="sm:col-span-2 xl:col-span-3">
            <dt className="text-slate-500">Latest LLM request</dt>
            <dd className="mt-1 text-slate-100">
              {brainStatus.latest_llm_request === null ? (
                <span className="text-slate-400">No LLM request has been recorded yet.</span>
              ) : (
                <pre className="overflow-x-auto rounded bg-black/30 p-3 text-xs text-slate-300">
                  {JSON.stringify(brainStatus.latest_llm_request, null, 2)}
                </pre>
              )}
            </dd>
          </div>
        </dl>
      )}

      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <div className="space-y-3">
          <h4 className="font-medium text-slate-200">Latest decision</h4>
          <DecisionSummaryCard decision={decision} />
        </div>
        <div className="space-y-3">
          <h4 className="font-medium text-slate-200">Latest plan</h4>
          <PlanCard plan={plan} />
        </div>
      </div>
    </section>
  );
}