"""Application service for recording and querying agent activity events."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.activity.models import AgentEvent, AgentEventType
from app.modules.activity.repository import AgentEventStore


class AgentEventService:
    """Record observable agent activity and serve it to the dashboard timeline."""

    def __init__(self, repository: AgentEventStore) -> None:
        self._repository = repository

    def record(
        self,
        *,
        agent_id: UUID,
        tick: int,
        event_type: AgentEventType,
        message: str,
        metadata: dict | None = None,
    ) -> AgentEvent:
        """Persist one activity event and return the stored entity."""
        event = AgentEvent(
            id=uuid4(),
            agent_id=agent_id,
            tick=tick,
            timestamp=datetime.now(UTC),
            event_type=event_type,
            message=message,
            metadata=metadata or {},
        )
        return self._repository.save(event)

    def list(
        self,
        agent_id: UUID | None = None,
        limit: int = 200,
        offset: int = 0,
    ) -> list[AgentEvent]:
        """Return a bounded page of activity events in chronological order."""
        return self._repository.list(agent_id=agent_id, limit=limit, offset=offset)