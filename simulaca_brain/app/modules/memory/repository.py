"""Persistence port for memory records."""

from typing import Protocol

from app.modules.memory.models import Memory


class MemoryRepository(Protocol):
    """Write-side persistence contract for the memory bounded context."""

    def save(self, memory: Memory) -> Memory:
        """Persist ``memory`` and return the durable record."""
