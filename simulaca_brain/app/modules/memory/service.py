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

    def recall(self, agent_id: UUID, goal: str, limit: int = 5) -> list[Memory]:
        """Return the most relevant memories for ``goal`` in deterministic rank order."""
        memories = self.list_memories(agent_id=agent_id, limit=100)
        relevant = [memory for memory in memories if self._matches_goal(memory, goal)]
        relevant.sort(key=lambda memory: self._recall_score(memory, goal), reverse=True)
        return relevant[:limit]

    def set_working_memory(self, agent_id: UUID, *, current_goal: str, current_action: str, target: str, started_at: datetime) -> Memory:
        """Replace the agent's current working-memory snapshot with the latest state."""
        for existing in self.list_memories(agent_id=agent_id, limit=100):
            if existing.memory_type is MemoryType.WORKING:
                self.delete_memory(existing.id)

        recalled = self.recall(agent_id=agent_id, goal=current_goal)
        selected_memory = recalled[0] if recalled else None
        working_content = f"Current thought: {current_goal}/{current_action}"
        if selected_memory is not None:
            working_content = f"{working_content} | Selected memory: {selected_memory.content}"

        return self.record(
            CreateMemoryRequest(
                agent_id=agent_id,
                memory_type=MemoryType.WORKING,
                content=working_content,
                tick=None,
                timestamp=started_at,
                event_type="working_memory",
                description=f"Goal={current_goal}; Action={current_action}; Target={target}",
                location=target,
                result="working_memory_updated",
                importance=0.5,
                metadata={
                    "current_goal": current_goal,
                    "current_action": current_action,
                    "target": target,
                    "recalled_memories": [memory.content for memory in recalled],
                    "selected_memory": selected_memory.content if selected_memory is not None else None,
                },
            )
        )

    @staticmethod
    def _matches_goal(memory: Memory, goal: str) -> bool:
        goal_value = goal.lower()
        if memory.event_type is not None and memory.event_type.lower() == goal_value:
            return True
        description = (memory.description or "").lower()
        return goal_value in description or goal_value in (memory.content.lower())

    @staticmethod
    def _recall_score(memory: Memory, goal: str) -> tuple[int, float, datetime]:
        relevance = 2 if (memory.event_type or "").lower() == goal.lower() else 1 if goal.lower() in (memory.content.lower() + " " + (memory.description or "").lower()) else 0
        return (relevance, memory.importance, memory.timestamp or memory.created_at)
