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
    attributes: dict[str, Any] = Field(default_factory=dict)


class Memory(CreateMemoryRequest):
    """A persisted memory record with provenance and creation time."""

    id: UUID
    created_at: datetime
