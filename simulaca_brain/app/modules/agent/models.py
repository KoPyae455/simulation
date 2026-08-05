"""Agent domain models and request/response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import Field, model_validator

from app.core.schemas import SimulacaBaseModel, TimestampedSchema
from app.modules.agent.state import AgentNeeds


class CreateAgentRequest(SimulacaBaseModel):
    """Input needed to introduce an autonomous agent to the world."""

    name: str = Field(min_length=1, max_length=100)
    needs: AgentNeeds = Field(default_factory=AgentNeeds)


class UpdateAgentRequest(SimulacaBaseModel):
    """Partial update for mutable agent state."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    needs: AgentNeeds | None = None

    @model_validator(mode="after")
    def require_change(self) -> "UpdateAgentRequest":
        """Reject empty patches, which otherwise have ambiguous client intent."""
        if self.name is None and self.needs is None:
            raise ValueError("At least one field must be provided for an update.")
        return self


class Agent(TimestampedSchema):
    """Persisted agent state exposed by the API."""

    id: UUID
    name: str
    needs: AgentNeeds


class PlanStep(SimulacaBaseModel):
    """A deterministic, inspectable action proposed for an agent."""

    action: str
    rationale: str
    priority: int = Field(ge=1)


class AgentPlan(SimulacaBaseModel):
    """Result of a planning cycle for one agent."""

    agent_id: UUID
    generated_at: datetime
    steps: list[PlanStep]
