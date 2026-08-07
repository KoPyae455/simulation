"""Build DecisionContext snapshots for planners."""

from datetime import datetime
from uuid import UUID

from app.modules.agent.models import Agent
from app.modules.cognition.action_registry import ActionRegistry
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.goal_generator import GoalGenerator
from app.modules.memory.service import MemoryService
from app.modules.world.models import Entity, Location
from app.modules.world.repository import WorldRepository
from app.modules.world.service import WorldPerceptionService


class ContextBuilder:
    """Assemble a bounded decision snapshot from live simulation state."""

    def __init__(
        self,
        perception: WorldPerceptionService,
        world_repository: WorldRepository,
        memory_service: MemoryService | None = None,
        goal_generator: GoalGenerator | None = None,
    ) -> None:
        self._perception = perception
        self._world_repository = world_repository
        self._memory_service = memory_service
        self._goal_generator = goal_generator or GoalGenerator()

    def build(
        self,
        agent: Agent,
        *,
        tick: int,
        simulation_datetime: datetime,
        goal: str | None = None,
    ) -> DecisionContext:
        """Create a decision context for ``agent`` at the current tick."""
        selected_goal = goal or self._goal_generator.generate(agent.needs)
        perception = self._perception.perceive(agent.id)
        current_location = self._resolve_location(perception.get("location"))
        nearby_locations = self._resolve_locations(perception.get("nearby_locations", []))
        nearby_entities = self._resolve_entities(perception.get("nearby_entities", []))
        relevant_memories = []
        if self._memory_service is not None:
            relevant_memories = self._memory_service.recall(agent.id, selected_goal)

        return DecisionContext(
            agent_id=agent.id,
            agent_name=agent.name,
            tick=tick,
            simulation_datetime=simulation_datetime,
            needs=agent.needs.model_copy(deep=True),
            personality=None,
            current_location=current_location,
            current_goal=selected_goal,
            relevant_memories=relevant_memories,
            nearby_locations=nearby_locations,
            nearby_entities=nearby_entities,
            world_facts={"connected_location_count": len(nearby_locations)},
            available_actions=list(ActionRegistry.list_actions()),
            action_constraints={"allowed_location_names": [loc.name for loc in nearby_locations]},
        )

    def _resolve_location(self, location_id: str | None) -> Location | None:
        if location_id is None:
            return None
        try:
            return self._world_repository.get_location(UUID(location_id))
        except Exception:
            return None

    @staticmethod
    def _resolve_locations(raw_locations: list[dict]) -> list[Location]:
        locations: list[Location] = []
        for item in raw_locations:
            try:
                locations.append(Location.model_validate(item))
            except Exception:
                continue
        return locations

    @staticmethod
    def _resolve_entities(raw_entities: list[dict]) -> list[Entity]:
        entities: list[Entity] = []
        for item in raw_entities:
            try:
                entities.append(Entity.model_validate(item))
            except Exception:
                continue
        return entities
