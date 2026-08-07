"""Domain models for world locations, entities, and overall state."""
from datetime import datetime
from typing import Dict, Any
from uuid import UUID

from pydantic import Field

from app.core.schemas import SimulacaBaseModel, TimestampedSchema


class Location(SimulacaBaseModel):
    id: UUID
    name: str
    description: str | None = None


class Entity(SimulacaBaseModel):
    id: UUID
    name: str
    location_id: UUID
    attributes: Dict[str, Any] = Field(default_factory=dict)


class WorldState(TimestampedSchema):
    current_simulation_datetime: datetime
    weather: str
    # Additional global fields can be added later
