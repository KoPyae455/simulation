"""Event-bus adapters that translate integration events into memory commands."""

from app.core.events import EventBus, EventSubscription
from app.modules.memory.events import MemoryWriteRequested
from app.modules.memory.models import CreateMemoryRequest
from app.modules.memory.service import MemoryService


class MemoryEventHandlers:
    """Handle memory write requests without coupling producers to ``MemoryService``."""

    def __init__(self, service: MemoryService) -> None:
        """Create handlers that delegate memory writes to ``service``."""
        self._service = service

    def register(self, event_bus: EventBus) -> EventSubscription:
        """Subscribe this handler set to the events it owns."""
        return event_bus.subscribe(MemoryWriteRequested, self.handle_memory_write_requested)

    def handle_memory_write_requested(self, event: MemoryWriteRequested) -> None:
        """Validate and persist a memory requested by another bounded context."""
        self._service.record(
            CreateMemoryRequest(
                agent_id=event.agent_id,
                memory_type=event.memory_type,
                content=event.content,
                attributes=dict(event.attributes),
            )
        )
