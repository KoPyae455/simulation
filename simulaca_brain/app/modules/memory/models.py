"""Domain models for long-lived and short-lived agent memory records."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import Field

from app.core.schemas import SimulacaBaseModel


class MemoryType(str, Enum):
    """Classifications that support distinct memory behavior in later milestones."""

    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"


class CreateMemoryRequest(SimulacaBaseModel):
    """Validated information required to record one agent memory."""

    agent_id: UUID
    memory_type: MemoryType
    content: str = Field(min_length=1)
    tick: int | None = None
    timestamp: datetime | None = None
    event_type: str | None = None
    description: str | None = None
    location: str | None = None
    result: str | None = None
    importance: float = Field(default=0.3, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)


class Memory(CreateMemoryRequest):
    """A persisted memory record with provenance and creation time."""

    id: UUID
    created_at: datetime


class MemorySummary(SimulacaBaseModel):
    """A compact view used by the dashboard for recent memories."""

    id: UUID
    agent_id: UUID
    memory_type: MemoryType
    content: str
    tick: int | None = None
    timestamp: datetime | None = None
    event_type: str | None = None
    description: str | None = None
    location: str | None = None
    result: str | None = None
    importance: float = 0.3
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    attributes: dict[str, Any] = Field(default_factory=dict)
