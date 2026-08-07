"""Tests for deterministic memory recall behavior."""

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.memory.models import Memory, MemoryType
from app.modules.memory.service import MemoryService


class InMemoryMemoryRepository:
    def __init__(self) -> None:
        self._memories: list[Memory] = []

    def save(self, memory: Memory) -> Memory:
        self._memories.append(memory)
        return memory

    def list(self, agent_id: object | None, limit: int) -> list[Memory]:
        memories = [memory for memory in self._memories if agent_id is None or memory.agent_id == agent_id]
        memories.sort(key=lambda item: item.created_at, reverse=True)
        return memories[:limit]

    def delete(self, memory_id: object) -> None:
        self._memories = [memory for memory in self._memories if memory.id != memory_id]


def test_memory_recall_filters_and_ranks_memories() -> None:
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository, event_bus=None)  # type: ignore[arg-type]
    agent_id = uuid4()

    repository.save(
        Memory(
            id=uuid4(),
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content="I drank water at the river.",
            tick=12,
            timestamp=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
            event_type="drink",
            description="Alice drank water.",
            location="river",
            result="thirst reduced",
            importance=0.9,
            metadata={"goal": "drink"},
            attributes={},
            created_at=datetime(2024, 1, 1, 12, 0, tzinfo=UTC),
        )
    )
    repository.save(
        Memory(
            id=uuid4(),
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content="I ate food at camp.",
            tick=11,
            timestamp=datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
            event_type="eat",
            description="Alice ate food.",
            location="camp",
            result="hunger reduced",
            importance=0.3,
            metadata={"goal": "eat"},
            attributes={},
            created_at=datetime(2024, 1, 1, 11, 0, tzinfo=UTC),
        )
    )

    recalled = service.recall(agent_id=agent_id, goal="drink", limit=5)

    assert len(recalled) == 1
    assert recalled[0].event_type == "drink"
    assert recalled[0].description == "Alice drank water."


def test_memory_recall_returns_empty_when_no_memories_match() -> None:
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository, event_bus=None)  # type: ignore[arg-type]
    agent_id = uuid4()

    recalled = service.recall(agent_id=agent_id, goal="sleep", limit=5)

    assert recalled == []
