"""Persisted decision logs associated with agent simulation outcomes."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from app.core.exceptions import RepositoryError
from app.core.schemas import SimulacaBaseModel
from app.modules.agent.state import AgentNeeds


class AgentDecisionLog(SimulacaBaseModel):
    """An inspectable action decision made for an agent during simulation."""

    id: UUID
    timestamp: datetime
    agent_id: UUID
    agent_name: str
    action: str
    reason: str
    internal_state_snapshot: AgentNeeds


class DecisionLogStore(Protocol):
    """Persistence port for agent decision logs."""

    def save(self, log: AgentDecisionLog) -> AgentDecisionLog:
        """Persist and return one decision log entry."""

    def list(self, agent_id: UUID | None, limit: int) -> list[AgentDecisionLog]:
        """Return recent decision logs, optionally scoped to one agent."""

    def clear(self) -> None:
        """Delete all persisted decision logs."""


class SqliteDecisionLogRepository:
    """SQLite adapter that keeps decision history separate from agent state."""

    def __init__(self, database_path: Path) -> None:
        """Create a repository backed by ``database_path``."""
        self._database_path = database_path

    def initialize(self) -> None:
        """Create the decision-log table idempotently."""
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS agent_decision_logs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    internal_state_json TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_decision_logs_agent_time "
                "ON agent_decision_logs (agent_id, timestamp DESC)"
            )

    def save(self, log: AgentDecisionLog) -> AgentDecisionLog:
        """Persist one log entry."""
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO agent_decision_logs VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(log.id),
                        log.timestamp.isoformat(),
                        str(log.agent_id),
                        log.agent_name,
                        log.action,
                        log.reason,
                        log.internal_state_snapshot.model_dump_json(),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to save the agent decision log.") from exc
        return log

    def list(self, agent_id: UUID | None, limit: int) -> list[AgentDecisionLog]:
        """Return the most recent bounded page in chronological display order."""
        query = "SELECT * FROM agent_decision_logs"
        parameters: tuple[str | int, ...] = (limit,)
        if agent_id is not None:
            query += " WHERE agent_id = ?"
            parameters = (str(agent_id), limit)
        query += " ORDER BY timestamp DESC LIMIT ?"

        try:
            with self._connect() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to load agent decision logs.") from exc
        return [self._to_log(row) for row in reversed(rows)]

    def clear(self) -> None:
        """Remove all stored decision logs."""
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM agent_decision_logs")
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to clear agent decision logs.") from exc

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_log(row: sqlite3.Row) -> AgentDecisionLog:
        return AgentDecisionLog(
            id=UUID(row["id"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            agent_id=UUID(row["agent_id"]),
            agent_name=row["agent_name"],
            action=row["action"],
            reason=row["reason"],
            internal_state_snapshot=AgentNeeds.model_validate(json.loads(row["internal_state_json"])),
        )
