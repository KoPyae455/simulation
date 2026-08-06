"""Unit tests for repository-backed memory behavior."""

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.memory.models import Memory, MemoryType
from app.modules.memory.repository import SqliteMemoryRepository


def test_memory_repository_saves_loads_orders_and_deletes_memories(tmp_path) -> None:
    repository = SqliteMemoryRepository(tmp_path / "memories.sqlite")
    repository.initialize()

    agent_id = uuid4()
    first = repository.save(
        Memory(
            id=uuid4(),
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content="First memory",
            attributes={"tick": 1},
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
        )
    )
    second = repository.save(
        Memory(
            id=uuid4(),
            agent_id=agent_id,
            memory_type=MemoryType.WORKING,
            content="Second memory",
            attributes={"tick": 2},
            created_at=datetime(2024, 1, 2, tzinfo=UTC),
        )
    )

    memories = repository.list(agent_id=agent_id, limit=10)
    assert [memory.content for memory in memories] == ["Second memory", "First memory"]

    repository.delete(second.id)
    remaining = repository.list(agent_id=agent_id, limit=10)
    assert [memory.content for memory in remaining] == ["First memory"]
