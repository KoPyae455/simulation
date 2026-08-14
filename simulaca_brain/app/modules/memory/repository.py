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

    def update(self, memory: Memory) -> Memory:
        """Persist updates to an existing memory and return the durable record."""


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
                    tick INTEGER,
                    timestamp TEXT,
                    event_type TEXT,
                    description TEXT,
                    location TEXT,
                    result TEXT,
                    importance REAL NOT NULL DEFAULT 0.3,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    attributes_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )"""
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_agent_created ON memories (agent_id, created_at DESC)"
            )
            self._migrate_legacy_schema(connection)

    def save(self, memory: Memory) -> Memory:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO memories (
                        id, agent_id, memory_type, content, tick, timestamp, event_type,
                        description, location, result, importance, metadata_json,
                        attributes_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(memory.id),
                        str(memory.agent_id),
                        memory.memory_type.value,
                        memory.content,
                        memory.tick,
                        memory.timestamp.isoformat() if memory.timestamp is not None else None,
                        memory.event_type,
                        memory.description,
                        memory.location,
                        memory.result,
                        memory.importance,
                        json.dumps(memory.metadata),
                        json.dumps(memory.attributes),
                        memory.created_at.isoformat(),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to save the agent memory.") from exc
        return memory

    def update(self, memory: Memory) -> Memory:
        try:
            with self._connect() as connection:
                result = connection.execute(
                    """
                    UPDATE memories
                    SET memory_type = ?,
                        content = ?,
                        tick = ?,
                        timestamp = ?,
                        event_type = ?,
                        description = ?,
                        location = ?,
                        result = ?,
                        importance = ?,
                        metadata_json = ?,
                        attributes_json = ?,
                        created_at = ?
                    WHERE id = ?
                    """,
                    (
                        memory.memory_type.value,
                        memory.content,
                        memory.tick,
                        memory.timestamp.isoformat() if memory.timestamp is not None else None,
                        memory.event_type,
                        memory.description,
                        memory.location,
                        memory.result,
                        memory.importance,
                        json.dumps(memory.metadata),
                        json.dumps(memory.attributes),
                        memory.created_at.isoformat(),
                        str(memory.id),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to update the agent memory.") from exc
        if result.rowcount == 0:
            raise RepositoryError(f"Memory {memory.id} was not found.")
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
        timestamp_raw = row["timestamp"] if "timestamp" in row.keys() else None
        metadata_raw = row["metadata_json"] if "metadata_json" in row.keys() else "{}"
        return Memory(
            id=UUID(row["id"]),
            agent_id=UUID(row["agent_id"]),
            memory_type=MemoryType(row["memory_type"]),
            content=row["content"],
            tick=row["tick"] if "tick" in row.keys() else None,
            timestamp=datetime.fromisoformat(timestamp_raw) if timestamp_raw else None,
            event_type=row["event_type"] if "event_type" in row.keys() else None,
            description=row["description"] if "description" in row.keys() else None,
            location=row["location"] if "location" in row.keys() else None,
            result=row["result"] if "result" in row.keys() else None,
            importance=float(row["importance"]) if "importance" in row.keys() else 0.3,
            metadata=json.loads(metadata_raw) if metadata_raw else {},
            attributes=json.loads(row["attributes_json"]) if row["attributes_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _migrate_legacy_schema(connection: sqlite3.Connection) -> None:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(memories)").fetchall()
        }
        migrations: list[tuple[str, str]] = [
            ("tick", "ALTER TABLE memories ADD COLUMN tick INTEGER"),
            ("timestamp", "ALTER TABLE memories ADD COLUMN timestamp TEXT"),
            ("event_type", "ALTER TABLE memories ADD COLUMN event_type TEXT"),
            ("description", "ALTER TABLE memories ADD COLUMN description TEXT"),
            ("location", "ALTER TABLE memories ADD COLUMN location TEXT"),
            ("result", "ALTER TABLE memories ADD COLUMN result TEXT"),
            ("importance", "ALTER TABLE memories ADD COLUMN importance REAL NOT NULL DEFAULT 0.3"),
            ("metadata_json", "ALTER TABLE memories ADD COLUMN metadata_json TEXT NOT NULL DEFAULT '{}'"),
            ("attributes_json", "ALTER TABLE memories ADD COLUMN attributes_json TEXT NOT NULL DEFAULT '{}'"),
        ]
        for column_name, statement in migrations:
            if column_name not in columns:
                connection.execute(statement)
