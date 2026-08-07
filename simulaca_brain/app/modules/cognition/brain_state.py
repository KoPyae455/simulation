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
    plan: ActionPlan | None = None
    executed_action: str | None = None
    latency_ms: int | None = None
    fallback_reason: str | None = None
    reasoning_summary: str | None = None
    model: str | None = None


class BrainStateStore:
    """Process-local store for brain status and recent decision metadata."""

    def __init__(self) -> None:
        self._latest_decisions: dict[UUID, AgentDecisionMetadata] = {}
        self._llm_request_logs: list[LLMRequestLogEntry] = []

    def record_decision(self, metadata: AgentDecisionMetadata) -> None:
        self._latest_decisions[metadata.agent_id] = metadata

    def get_decision(self, agent_id: UUID) -> AgentDecisionMetadata | None:
        return self._latest_decisions.get(agent_id)

    def record_llm_request(self, entry: LLMRequestLogEntry) -> None:
        self._llm_request_logs.append(entry)
        if len(self._llm_request_logs) > 500:
            self._llm_request_logs = self._llm_request_logs[-500:]

    def latest_llm_request(self) -> LLMRequestLogEntry | None:
        if not self._llm_request_logs:
            return None
        return self._llm_request_logs[-1]
