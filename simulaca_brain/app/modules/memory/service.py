"""Application service for recording agent memory."""

from datetime import UTC, datetime
from uuid import uuid4

from app.core.events import EventBus
from app.modules.memory.events import MemoryRecorded
from app.modules.memory.models import CreateMemoryRequest, Memory
from app.modules.memory.repository import MemoryRepository


class MemoryService:
    """Record memories through injected persistence and event-publication ports."""

    def __init__(self, repository: MemoryRepository, event_bus: EventBus) -> None:
        """Create the service with its persistence and integration dependencies."""
        self._repository = repository
        self._event_bus = event_bus

    def record(self, request: CreateMemoryRequest) -> Memory:
        """Persist a new memory and publish an event after persistence succeeds."""
        memory = Memory(
            id=uuid4(),
            agent_id=request.agent_id,
            memory_type=request.memory_type,
            content=request.content,
            attributes=request.attributes,
            created_at=datetime.now(UTC),
        )
        persisted_memory = self._repository.save(memory)
        self._event_bus.publish(MemoryRecorded(memory=persisted_memory))
        return persisted_memory
