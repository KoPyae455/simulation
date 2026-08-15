"""SQLite-backed repository for world locations, entities, and connections."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from app.core.exceptions import RepositoryError, EntityNotFoundError
from app.modules.world.models import Location, Entity, Resource


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

    def create_resource(self, name: str, location_id: UUID, attributes: dict | None = None) -> Resource:
        ...

    def list_resources(self, location_id: UUID | None = None) -> list[Resource]:
        ...

    def get_resource(self, resource_id: UUID) -> Resource:
        ...

    def update_resource(self, resource: Resource) -> None:
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
            conn.execute(
                """CREATE TABLE IF NOT EXISTS resources (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, location_id TEXT NOT NULL,
                    affordances_json TEXT NOT NULL, water_available INTEGER NOT NULL DEFAULT 1,
                    food_quantity INTEGER NOT NULL DEFAULT 0
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

    def create_resource(self, name: str, location_id: UUID, attributes: dict | None = None) -> Resource:
        res_id = uuid4()
        affs = attributes.get("affordances", []) if attributes else []
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO resources VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        str(res_id),
                        name,
                        str(location_id),
                        json.dumps(affs),
                        1 if attributes.get("water_available", True) else 0,
                        attributes.get("food_quantity", 0),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to create resource") from exc
        return Resource(
            id=res_id,
            name=name,
            location_id=location_id,
            affordances=set(affs) if affs else set(),
            water_available=attributes.get("water_available", True),
            food_quantity=attributes.get("food_quantity", 0),
        )

    def list_resources(self, location_id: UUID | None = None) -> list[Resource]:
        import json
        try:
            with self._connect() as conn:
                if location_id is not None:
                    rows = conn.execute(
                        "SELECT * FROM resources WHERE location_id = ? ORDER BY name ASC",
                        (str(location_id),),
                    ).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM resources ORDER BY name ASC").fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to list resources") from exc
        return [
            Resource(
                id=UUID(r["id"]),
                name=r["name"],
                location_id=UUID(r["location_id"]),
                affordances=set(json.loads(r["affordances_json"])) if json.loads(r["affordances_json"]) else set(),
                water_available=bool(r["water_available"]),
                food_quantity=int(r["food_quantity"]),
            )
            for r in rows
        ]

    def get_resource(self, resource_id: UUID) -> Resource:
        import json
        try:
            with self._connect() as conn:
                row = conn.execute("SELECT * FROM resources WHERE id = ?", (str(resource_id),)).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to load resource") from exc
        if row is None:
            raise EntityNotFoundError("Resource", resource_id)
        return Resource(
            id=UUID(row["id"]),
            name=row["name"],
            location_id=UUID(row["location_id"]),
            affordances=set(json.loads(row["affordances_json"])) if json.loads(row["affordances_json"]) else set(),
            water_available=bool(row["water_available"]),
            food_quantity=int(row["food_quantity"]),
        )

    def update_resource(self, resource: Resource) -> None:
        import json
        try:
            with self._connect() as conn:
                conn.execute(
                    """UPDATE resources SET
                        name = ?, location_id = ?, affordances_json = ?, water_available = ?,
                        food_quantity = ?
                        WHERE id = ?""",
                    (
                        resource.name,
                        str(resource.location_id),
                        json.dumps(list(resource.affordances)),
                        1 if resource.water_available else 0,
                        resource.food_quantity,
                        str(resource.id),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError("Unable to update resource") from exc

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._database_path)
        conn.row_factory = sqlite3.Row
        return conn
