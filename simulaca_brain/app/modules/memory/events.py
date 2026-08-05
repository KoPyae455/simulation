"""Events owned by the memory bounded context."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.modules.memory.models import Memory, MemoryType


@dataclass(frozen=True, slots=True)
class MemoryWriteRequested:
    """Request that the memory module record information for an agent."""

    agent_id: UUID
    memory_type: MemoryType
    content: str
    attributes: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MemoryRecorded:
    """Event emitted after a memory record has been durably saved."""

    memory: Memory
