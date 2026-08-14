"""SQLite-backed persistence for the agent activity timeline."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.core.exceptions import RepositoryError
from app.modules.activity.models import AgentEvent, AgentEventType


class AgentEventStore(Protocol):
    """Persistence port for agent activity events."""

    def save(self, event: AgentEvent) -> AgentEvent:
        """Persist and return one activity event."""

    def list(self, agent_id: UUID | None, limit: int, offset: int) -> list[AgentEvent]:
        """Return a bounded page of activity events in chronological display order."""


class SqliteAgentEventRepository:
    """SQLite adapter that keeps the activity timeline separate from other state."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        """Create the event table and its lookup index idempotently."""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_events (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    tick INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_events_agent_time "
                "ON agent_events (agent_id, timestamp DESC)"
            )

    def save(self, event: AgentEvent) -> AgentEvent:
        """Persist one activity event."""
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO agent_events VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(event.id),
                        str(event.agent_id),
                        event.tick,
                        event.timestamp.isoformat(),
                        event.event_type.value,
                        event.message,
                        json.dumps(event.metadata),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to save the agent activity event.") from exc
        return event

    def list(self, agent_id: UUID | None, limit: int, offset: int) -> list[AgentEvent]:
        """Return the newest bounded page of events in chronological display order.

        Newest events are selected first (for pagination), then reversed so the
        returned list reads oldest → newest like the browser timeline.
        """
        query = "SELECT * FROM agent_events"
        parameters: tuple[object, int, int] = (limit, offset)
        if agent_id is not None:
            query += " WHERE agent_id = ?"
            parameters = (str(agent_id), limit, offset)
        query += " ORDER BY rowid DESC LIMIT ? OFFSET ?"

        try:
            with self._connect() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to load agent activity events.") from exc
        return [self._to_event(row) for row in reversed(rows)]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_event(row: sqlite3.Row) -> AgentEvent:
        return AgentEvent(
            id=UUID(row["id"]),
            agent_id=UUID(row["agent_id"]),
            tick=row["tick"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            event_type=AgentEventType(row["event_type"]),
            message=row["message"],
            metadata=json.loads(row["metadata_json"]),
        )