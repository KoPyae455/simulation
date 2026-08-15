"""In-memory metadata for recent planner and LLM activity."""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.modules.cognition.action_plan import ActionPlan


@dataclass(slots=True)
class LLMRequestLogEntry:
    """Safe metadata captured for one LLM planning attempt."""

    agent_id: UUID
    tick: int
    model: str
    planner_type: str
    latency_ms: int | None
    status: str
    error_type: str | None = None
    plan_id: UUID | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now())


@dataclass(slots=True)
class AgentDecisionMetadata:
    """Latest decision metadata exposed through the API and dashboard."""

    agent_id: UUID
    agent_name: str
    tick: int
    timestamp: datetime
    planner_type: str
    goal: str
    status: str
    agent_status: str | None = None
    plan: ActionPlan | None = None
    executed_action: str | None = None
    latency_ms: int | None = None
    fallback_reason: str | None = None
    reasoning_summary: str | None = None
    model: str | None = None

    def to_public_dict(self) -> dict:
        """Serialize only client-safe metadata, never prompts or chain-of-thought."""
        plan_payload = None
        if self.plan is not None:
            plan_payload = {
                "plan_id": str(self.plan.plan_id),
                "goal": self.plan.goal,
                "reasoning_summary": self.plan.reasoning_summary,
                "steps": [
                    {
                        "action": step.action,
                        "target": step.target,
                        "parameters": step.parameters,
                    }
                    for step in self.plan.steps
                ],
            }
        return {
            "agent_id": str(self.agent_id),
            "agent_name": self.agent_name,
            "tick": self.tick,
            "timestamp": self.timestamp.isoformat(),
            "planner": self.planner_type,
            "goal": self.goal,
            "status": self.status,
            "agent_status": self.agent_status,
            "plan": plan_payload,
            "executed_action": self.executed_action,
            "latency_ms": self.latency_ms,
            "fallback_reason": self.fallback_reason,
            "reasoning_summary": self.reasoning_summary,
            "model": self.model,
        }


class BrainStateStore:
    """Process-local store for brain status and recent decision metadata."""

    def __init__(self) -> None:
        self._latest_decisions: dict[UUID, AgentDecisionMetadata] = {}
        self._llm_request_logs: list[LLMRequestLogEntry] = []
        self._step_indexes: dict[UUID, int] = {}

    def record_decision(self, metadata: AgentDecisionMetadata) -> None:
        self._latest_decisions[metadata.agent_id] = metadata

    def get_decision(self, agent_id: UUID) -> AgentDecisionMetadata | None:
        return self._latest_decisions.get(agent_id)

    def current_step_index(self, agent_id: UUID) -> int:
        """Return the next plan step index to execute for ``agent_id``."""
        return self._step_indexes.get(agent_id, 0)

    def set_step_index(self, agent_id: UUID, index: int) -> None:
        """Record the plan step index to execute on the following tick."""
        self._step_indexes[agent_id] = max(0, index)

    def reset_step_index(self, agent_id: UUID) -> None:
        """Reset an agent's plan cursor, e.g. when a fresh plan is generated."""
        self._step_indexes[agent_id] = 0

    def all_decisions(self) -> list[AgentDecisionMetadata]:
        """Return all stored decisions in insertion-stable order."""
        return list(self._latest_decisions.values())

    def record_llm_request(self, entry: LLMRequestLogEntry) -> None:
        self._llm_request_logs.append(entry)
        if len(self._llm_request_logs) > 500:
            self._llm_request_logs = self._llm_request_logs[-500:]

    def latest_llm_request(self) -> LLMRequestLogEntry | None:
        if not self._llm_request_logs:
            return None
        return self._llm_request_logs[-1]
