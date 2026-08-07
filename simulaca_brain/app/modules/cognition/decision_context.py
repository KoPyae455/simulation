"""Structured decision input passed to planners."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.core.schemas import SimulacaBaseModel
from app.modules.agent.state import AgentNeeds
from app.modules.memory.models import Memory
from app.modules.world.models import Entity, Location


class DecisionContext(SimulacaBaseModel):
    """Everything a planner needs to propose one action plan."""

    agent_id: UUID
    agent_name: str
    tick: int
    simulation_datetime: datetime
    needs: AgentNeeds
    personality: dict[str, Any] | None = None
    current_location: Location | None = None
    current_goal: str
    relevant_memories: list[Memory] = Field(default_factory=list)
    nearby_locations: list[Location] = Field(default_factory=list)
    nearby_entities: list[Entity] = Field(default_factory=list)
    world_facts: dict[str, Any] = Field(default_factory=dict)
    available_actions: list[str] = Field(default_factory=list)
    action_constraints: dict[str, Any] = Field(default_factory=dict)
