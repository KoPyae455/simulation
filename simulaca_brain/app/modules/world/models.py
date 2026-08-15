"""Domain models for world locations, entities, and overall state."""
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from pydantic import Field

from app.core.schemas import SimulacaBaseModel, TimestampedSchema


class Location(SimulacaBaseModel):
    """A location in the simulated world."""

    id: UUID
    name: str
    description: str | None = None

    model_config = {"alias_generator": None}


class Entity(SimulacaBaseModel):
    """A world entity (e.g., water, food, objects) at a location."""

    id: UUID
    name: str
    location_id: UUID
    attributes: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"alias_generator": None}


class Resource(SimulacaBaseModel):
    """A world resource or object with state and affordances."""

    id: UUID
    name: str
    description: str | None = None
    location_id: UUID
    # Affordances: what actions this resource supports
    affordances: set[str] = Field(default_factory=set)
    # Resource state
    water_available: bool = Field(default=True, description="Whether drinkable water is available")
    food_quantity: int = Field(
        default=0, ge=0, le=100, description="Amount of edible food (0=none)"
    )
    # General attributes for LLM/context queries
    attributes: Dict[str, Any] = Field(default_factory=dict)

    model_config = {"alias_generator": None}


class WorldState(TimestampedSchema):
    """Global world state."""

    current_simulation_datetime: datetime
    weather: str = "clear"
    # Global resource tracking can be added here later
