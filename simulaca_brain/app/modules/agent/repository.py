"""SQLite persistence adapter for agent state."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.core.exceptions import EntityNotFoundError, RepositoryError
from app.modules.agent.models import Agent, AgentNeeds, CreateAgentRequest, UpdateAgentRequest


class AgentRepository:
    """Owns agent SQL, isolating services from a specific storage engine."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        """Create the table idempotently for local SQLite deployments."""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, needs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                )"""
            )

    def create(self, request: CreateAgentRequest) -> Agent:
        """Persist and return a new agent."""
        agent_id, now = uuid4(), datetime.now(UTC)
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO agents VALUES (?, ?, ?, ?, ?)",
                    (str(agent_id), request.name, request.needs.model_dump_json(), now.isoformat(), now.isoformat()),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to save agent.") from exc
        return Agent(id=agent_id, name=request.name, needs=request.needs, created_at=now, updated_at=now)

    def get(self, agent_id: UUID) -> Agent:
        """Load an agent or raise a client-safe not-found error."""
        try:
            with self._connect() as connection:
                row = connection.execute("SELECT * FROM agents WHERE id = ?", (str(agent_id),)).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to load agent.") from exc
        if row is None:
            raise EntityNotFoundError("Agent", agent_id)
        return self._to_agent(row)

    def list(self, limit: int, offset: int) -> list[Agent]:
        """Return a stable, bounded page of agents."""
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT * FROM agents ORDER BY created_at ASC LIMIT ? OFFSET ?", (limit, offset)
                ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to list agents.") from exc
        return [self._to_agent(row) for row in rows]

    def update(self, agent_id: UUID, request: UpdateAgentRequest) -> Agent:
        """Apply a validated partial update and return the resulting state."""
        existing = self.get(agent_id)
        name = request.name if request.name is not None else existing.name
        needs = request.needs if request.needs is not None else existing.needs
        updated_at = datetime.now(UTC)
        try:
            with self._connect() as connection:
                connection.execute(
                    "UPDATE agents SET name = ?, needs_json = ?, updated_at = ? WHERE id = ?",
                    (name, needs.model_dump_json(), updated_at.isoformat(), str(agent_id)),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to update agent.") from exc
        return Agent(id=agent_id, name=name, needs=needs, created_at=existing.created_at, updated_at=updated_at)

    def delete(self, agent_id: UUID) -> None:
        """Remove one agent, reporting a not-found error for an unknown identifier."""
        try:
            with self._connect() as connection:
                result = connection.execute("DELETE FROM agents WHERE id = ?", (str(agent_id),))
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to delete agent.") from exc
        if result.rowcount == 0:
            raise EntityNotFoundError("Agent", agent_id)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_agent(row: sqlite3.Row) -> Agent:
        return Agent(
            id=UUID(row["id"]), name=row["name"], needs=AgentNeeds.model_validate(json.loads(row["needs_json"])),
            created_at=datetime.fromisoformat(row["created_at"]), updated_at=datetime.fromisoformat(row["updated_at"]),
        )
