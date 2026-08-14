"""Domain models for the agent activity timeline (observability V0.7.1)."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from app.core.schemas import SimulacaBaseModel


class AgentEventType(str, Enum):
    """Stable identifiers for observable agent/world events."""

    NEED_CHANGED = "need_changed"
    GOAL_CHANGED = "goal_changed"
    DECISION = "decision"
    PLAN_CREATED = "plan_created"
    ACTION_STARTED = "action_started"
    ACTION_COMPLETED = "action_completed"
    STATE_CHANGED = "state_changed"
    MEMORY_CREATED = "memory_created"
    REFLECTION = "reflection"
    KNOWLEDGE = "knowledge"
    ERROR = "error"
    FALLBACK = "fallback"


class AgentEvent(SimulacaBaseModel):
    """One concise, observable activity record for an agent timeline."""

    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    tick: int = Field(ge=0)
    timestamp: datetime
    event_type: AgentEventType
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)