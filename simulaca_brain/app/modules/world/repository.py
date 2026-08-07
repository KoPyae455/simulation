"""SQLite-backed repository for world locations, entities, and connections."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from app.core.exceptions import RepositoryError, EntityNotFoundError
from app.modules.world.models import Location, Entity


class WorldRepository(Protocol):
    def create_location(self, name: str, description: str | None) -> Location:
        ...

    def list_locations(self) -> list[Location]:
        ...

    def get_location(self, location_id: UUID) -> Location:
        ...

    def connect_locations(self, a: UUID, b: UUID) -> None:
        ...

    def create_entity(self, name: str, location_id: UUID, attributes: dict) -> Entity:
        ...

    def list_entities(self) -> list[Entity]:
        ...

    def set_agent_location(self, agent_id: UUID, location_id: UUID) -> None:
        ...

    def get_agent_location(self, agent_id: UUID) -> UUID | None:
        ...


class SqliteWorldRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    def initialize(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS locations (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS location_connections (
                    a TEXT NOT NULL, b TEXT NOT NULL,
                    UNIQUE(a,b)
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, location_id TEXT NOT NULL, attributes_json TEXT NOT NULL
                )"""
            )
            conn.execute(
                """CREATE TABLE IF NOT EXISTS agent_locations (
                    agent_id TEXT PRIMARY KEY, location_id TEXT NOT NULL
                )"""
            )

    def create_location(self, name: str, description: str | None) -> Location:
        loc_id = uuid4()
        try:
            with self._connect() as conn:
                conn.execute("INSERT INTO locations VALUES (?, ?, ?)", (str(loc_id), name, description))
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to create location") from exc
        return Location(id=loc_id, name=name, description=description)

    def list_locations(self) -> list[Location]:
        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM locations ORDER BY name ASC").fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to list locations") from exc
        return [Location(id=UUID(r["id"]), name=r["name"], description=r["description"]) for r in rows]

    def get_location(self, location_id: UUID) -> Location:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM locations WHERE id = ?", (str(location_id),)).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to load location") from exc
        if row is None:
            raise EntityNotFoundError("Location", location_id)
        return Location(id=UUID(row["id"]), name=row["name"], description=row["description"])

    def connect_locations(self, a: UUID, b: UUID) -> None:
        # store both directions but enforce uniqueness
        try:
            with self._connect() as conn:
                conn.execute("INSERT OR IGNORE INTO location_connections VALUES (?, ?)", (str(a), str(b)))
                conn.execute("INSERT OR IGNORE INTO location_connections VALUES (?, ?)", (str(b), str(a)))
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to connect locations") from exc

    def get_connected_locations(self, location_id: UUID) -> list[Location]:
        try:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT l.* FROM location_connections c JOIN locations l ON c.b = l.id WHERE c.a = ? ORDER BY l.name ASC",
                    (str(location_id),),
                ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to load connected locations") from exc
        return [Location(id=UUID(r["id"]), name=r["name"], description=r["description"]) for r in rows]

    def create_entity(self, name: str, location_id: UUID, attributes: dict) -> Entity:
        ent_id = uuid4()
        import json

        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO entities VALUES (?, ?, ?, ?)", (str(ent_id), name, str(location_id), json.dumps(attributes))
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to create entity") from exc
        return Entity(id=ent_id, name=name, location_id=location_id, attributes=attributes)

    def list_entities(self) -> list[Entity]:
        import json

        try:
            with self._connect() as conn:
                rows = conn.execute("SELECT * FROM entities ORDER BY name ASC").fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to list entities") from exc
        return [Entity(id=UUID(r["id"]), name=r["name"], location_id=UUID(r["location_id"]), attributes=json.loads(r["attributes_json"])) for r in rows]

    def set_agent_location(self, agent_id: UUID, location_id: UUID) -> None:
        try:
            with self._connect() as conn:
                conn.execute("INSERT OR REPLACE INTO agent_locations VALUES (?, ?)", (str(agent_id), str(location_id)))
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to set agent location") from exc

    def get_agent_location(self, agent_id: UUID) -> UUID | None:
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT location_id FROM agent_locations WHERE agent_id = ?", (str(agent_id),)).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to get agent location") from exc
        return UUID(row["location_id"]) if row is not None else None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        return conn
