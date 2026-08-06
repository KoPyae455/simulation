"""Persistence port for memory records."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.core.exceptions import RepositoryError
from app.modules.memory.models import Memory, MemoryType


class MemoryRepository(Protocol):
    """Persistence contract for the memory bounded context."""

    def save(self, memory: Memory) -> Memory:
        """Persist ``memory`` and return the durable record."""

    def list(self, agent_id: UUID | None, limit: int) -> list[Memory]:
        """Return the most recent memories, optionally scoped to one agent."""

    def delete(self, memory_id: UUID) -> None:
        """Delete one memory record by identifier."""


class SqliteMemoryRepository:
    """SQLite-backed memory repository for durable, queryable memory storage."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    attributes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_agent_created ON memories (agent_id, created_at DESC)"
            )

    def save(self, memory: Memory) -> Memory:
        try:
            with self._connect() as connection:
                connection.execute(
                    "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(memory.id),
                        str(memory.agent_id),
                        memory.memory_type.value,
                        memory.content,
                        json.dumps(memory.attributes),
                        memory.created_at.isoformat(),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to save the agent memory.") from exc
        return memory

    def list(self, agent_id: UUID | None, limit: int) -> list[Memory]:
        query = "SELECT * FROM memories"
        parameters: tuple[str | int, ...] = (limit,)
        if agent_id is not None:
            query += " WHERE agent_id = ?"
            parameters = (str(agent_id), limit)
        query += " ORDER BY created_at DESC LIMIT ?"

        try:
            with self._connect() as connection:
                rows = connection.execute(query, parameters).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to load agent memories.") from exc
        return [self._to_memory(row) for row in rows]

    def delete(self, memory_id: UUID) -> None:
        try:
            with self._connect() as connection:
                result = connection.execute("DELETE FROM memories WHERE id = ?", (str(memory_id),))
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to delete the agent memory.") from exc
        if result.rowcount == 0:
            raise RepositoryError(f"Memory {memory_id} was not found.")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _to_memory(row: sqlite3.Row) -> Memory:
        return Memory(
            id=UUID(row["id"]),
            agent_id=UUID(row["agent_id"]),
            memory_type=MemoryType(row["memory_type"]),
            content=row["content"],
            attributes=json.loads(row["attributes_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
