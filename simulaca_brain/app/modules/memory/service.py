"""Application service for recording and reading agent memory."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.events import EventBus
from app.modules.memory.events import MemoryRecorded
from app.modules.memory.models import CreateMemoryRequest, Memory, MemoryType
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
            tick=request.tick,
            timestamp=request.timestamp,
            event_type=request.event_type,
            description=request.description,
            location=request.location,
            result=request.result,
            importance=request.importance,
            metadata=request.metadata,
            attributes=request.attributes,
            created_at=request.timestamp or datetime.now(UTC),
        )
        persisted_memory = self._repository.save(memory)
        self._event_bus.publish(MemoryRecorded(memory=persisted_memory))
        return persisted_memory

    def list_memories(self, agent_id: UUID | None = None, limit: int = 20) -> list[Memory]:
        """Return the most recent memory records, optionally filtered to one agent."""
        return self._repository.list(agent_id=agent_id, limit=limit)

    def recent_memories(self, agent_id: UUID | None = None, limit: int = 20) -> list[Memory]:
        """Return the most recent memory records in newest-first order."""
        return self.list_memories(agent_id=agent_id, limit=limit)

    def delete_memory(self, memory_id: UUID) -> None:
        """Remove one memory record from storage."""
        self._repository.delete(memory_id)

    def set_working_memory(self, agent_id: UUID, *, current_goal: str, current_action: str, target: str, started_at: datetime) -> Memory:
        """Replace the agent's current working-memory snapshot with the latest state."""
        for existing in self.list_memories(agent_id=agent_id, limit=100):
            if existing.memory_type is MemoryType.WORKING:
                self.delete_memory(existing.id)

        return self.record(
            CreateMemoryRequest(
                agent_id=agent_id,
                memory_type=MemoryType.WORKING,
                content=f"Current thought: {current_goal}/{current_action}",
                tick=None,
                timestamp=started_at,
                event_type="working_memory",
                description=f"Goal={current_goal}; Action={current_action}; Target={target}",
                location=target,
                result="working_memory_updated",
                importance=0.5,
                metadata={"current_goal": current_goal, "current_action": current_action, "target": target},
            )
        )
