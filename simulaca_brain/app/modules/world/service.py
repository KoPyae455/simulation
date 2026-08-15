"""Application services for world knowledge and perception."""
from typing import List, Optional
from uuid import UUID

from app.modules.world.models import Location, Entity, Resource
from app.modules.world.repository import WorldRepository


class WorldKnowledgeService:
    """Answer queries about the persistent world state."""

    def __init__(self, repository: WorldRepository) -> None:
        self._repo = repository

    def list_locations(self) -> List[Location]:
        return self._repo.list_locations()

    def get_location(self, location_id: UUID) -> Location:
        return self._repo.get_location(location_id)

    def list_entities(self) -> List[Entity]:
        return self._repo.list_entities()

    def connect_locations(self, a: UUID, b: UUID) -> None:
        self._repo.connect_locations(a, b)

    def create_location(self, name: str, description: str | None = None) -> Location:
        return self._repo.create_location(name, description)

    def create_entity(self, name: str, location_id: UUID, attributes: dict | None = None) -> Entity:
        return self._repo.create_entity(name, location_id, attributes or {})

    def list_resources(self, location_id: UUID | None = None) -> List[Resource]:
        return self._repo.list_resources(location_id)


class WorldPerceptionService:
    """Determine what an agent can perceive from its location."""

    def __init__(self, knowledge: WorldKnowledgeService, repository: WorldRepository) -> None:
        self._knowledge = knowledge
        self._repo = repository

    def perceive(self, agent_id: UUID) -> dict:
        """Return a perception bundle for the agent.

        Perception is LOCAL: agents only see their current location and
        directly connected locations. They do NOT see locations far away.
        """
        location_id = self._repo.get_agent_location(agent_id)
        if location_id is None:
            return {
                "location": None,
                "nearby_locations": [],
                "nearby_entities": [],
                "nearby_resources": [],
            }

        nearby_locations = self._repo.get_connected_locations(location_id)
        # include current location as well
        try:
            current_loc = self._knowledge.get_location(location_id)
            nearby_locations = [current_loc] + [l for l in nearby_locations if l.id != current_loc.id]
        except Exception:
            nearby_locations = [loc for loc in self._repo.get_connected_locations(location_id) if loc.id != location_id]

        # gather entities at current and nearby locations
        all_entities = self._knowledge.list_entities()
        nearby_entities = [e for e in all_entities if e.location_id == location_id or any(e.location_id == l.id for l in nearby_locations)]

        # gather resources at current and nearby locations - LOCAL perception
        all_resources = self._knowledge.list_resources()
        nearby_resources = [r for r in all_resources if r.location_id == location_id or any(r.location_id == l.id for l in nearby_locations)]

        return {
            "location": str(location_id),
            "nearby_locations": [l.model_dump() for l in nearby_locations],
            "nearby_entities": [e.model_dump() for e in nearby_entities],
            "nearby_resources": [r.model_dump() for r in nearby_resources],
        }
