"""Unit tests for write-oriented memory module behavior."""

from dataclasses import dataclass, field
from uuid import uuid4

from app.core.events import InMemoryEventBus
from app.modules.memory.event_handlers import MemoryEventHandlers
from app.modules.memory.events import MemoryRecorded, MemoryWriteRequested
from app.modules.memory.models import CreateMemoryRequest, Memory, MemoryType
from app.modules.memory.service import MemoryService


@dataclass
class InMemoryMemoryRepository:
    """Test persistence adapter that retains saved memory records."""

    saved_memories: list[Memory] = field(default_factory=list)

    def save(self, memory: Memory) -> Memory:
        """Retain and return the supplied memory record."""
        self.saved_memories.append(memory)
        return memory


def test_memory_service_records_and_publishes_memory() -> None:
    """A successful write persists the record before emitting its event."""
    event_bus = InMemoryEventBus()
    repository = InMemoryMemoryRepository()
    service = MemoryService(repository, event_bus)
    recorded_events: list[MemoryRecorded] = []
    event_bus.subscribe(MemoryRecorded, recorded_events.append)
    agent_id = uuid4()

    memory = service.record(
        CreateMemoryRequest(
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content="Observed a sunrise.",
        )
    )

    assert repository.saved_memories == [memory]
    assert recorded_events == [MemoryRecorded(memory)]


def test_memory_event_handler_records_a_requested_memory() -> None:
    """Other modules request memory writes through events rather than direct calls."""
    event_bus = InMemoryEventBus()
    repository = InMemoryMemoryRepository()
    handlers = MemoryEventHandlers(MemoryService(repository, event_bus))
    handlers.register(event_bus)
    agent_id = uuid4()

    event_bus.publish(
        MemoryWriteRequested(
            agent_id=agent_id,
            memory_type=MemoryType.WORKING,
            content="The shelter is nearby.",
            attributes={"source": "perception"},
        )
    )

    assert len(repository.saved_memories) == 1
    assert repository.saved_memories[0].agent_id == agent_id
    assert repository.saved_memories[0].memory_type is MemoryType.WORKING
