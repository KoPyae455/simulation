"""Unit tests for the agent activity timeline (observability V0.7.1)."""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from app.core.events import InMemoryEventBus
from app.modules.activity.models import AgentEventType
from app.modules.activity.repository import SqliteAgentEventRepository
from app.modules.activity.service import AgentEventService
from app.modules.agent.logs import AgentDecisionLog
from app.modules.agent.models import Agent, UpdateAgentRequest
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.brain_service import BrainService
from app.modules.cognition.brain_state import BrainStateStore
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.llm_planner import LLMPlanner
from app.modules.cognition.plan_executor import PlanExecutor
from app.modules.cognition.plan_validator import PlanValidator
from app.modules.cognition.planner import RuleBasedPlanner
from app.modules.cognition.planner_service import CompositePlanner
from app.core.llm.fake import FakeLLMProvider
from app.modules.memory.models import CreateMemoryRequest, Memory, MemoryType
from app.modules.memory.service import MemoryService
from app.modules.simulation.service import SimulationService
from app.modules.world.clock import SimulationClock
from app.modules.world.models import Entity, Location

VALID_LLM_PLAN = json.dumps(
    {
        "goal": "drink",
        "reasoning_summary": "The agent is thirsty and water is at the river.",
        "steps": [
            {"action": "move", "target": "River", "parameters": {}},
            {"action": "drink", "target": "River", "parameters": {}},
        ],
    }
)


def _event_service(tmp_path) -> AgentEventService:
    repository = SqliteAgentEventRepository(tmp_path / "events.sqlite")
    repository.initialize()
    return AgentEventService(repository)


def _context(home: Location, river: Location) -> DecisionContext:
    return DecisionContext(
        agent_id=uuid4(),
        agent_name="Alice",
        tick=1,
        simulation_datetime=datetime(2024, 1, 1, tzinfo=UTC),
        needs=AgentNeeds(thirst=95),
        current_location=home,
        current_goal="drink",
        nearby_locations=[home, river],
        nearby_entities=[
            Entity(id=uuid4(), name="Water", location_id=river.id, attributes={"drinkable": True})
        ],
        available_actions=["move", "drink", "eat", "sleep", "idle"],
        action_constraints={"allowed_location_names": ["Home", "River"]},
)
# --- Simulation generates events ------------------------------------------


class RecordingAgentStore:
    def __init__(self, agent: Agent) -> None:
        self._agent = agent

    def list(self, limit: int, offset: int) -> list[Agent]:
        return [self._agent]

    def update(self, agent_id: object, request: UpdateAgentRequest) -> Agent:
        self._agent = Agent(
            id=self._agent.id,
            name=request.name or self._agent.name,
            needs=request.needs or self._agent.needs,
            created_at=self._agent.created_at,
            updated_at=self._agent.updated_at,
        )
        return self._agent


class RecordingDecisionLogStore:
    def __init__(self) -> None:
        self.logs: list[AgentDecisionLog] = []

    def save(self, log: AgentDecisionLog) -> AgentDecisionLog:
        self.logs.append(log)
        return log

    def list(self, agent_id: object, limit: int) -> list[AgentDecisionLog]:
        return self.logs

    def clear(self) -> None:
        self.logs.clear()


def test_simulation_generates_need_goal_and_state_events(tmp_path) -> None:
    agent = Agent(
        id=uuid4(),
        name="Alice",
        needs=AgentNeeds(thirst=95),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=None,
    )
    events = _event_service(tmp_path)
    clock = SimulationClock(datetime(2024, 1, 1, tzinfo=UTC), tick_duration=timedelta(minutes=1))
    service = SimulationService(
        RecordingAgentStore(agent),
        RecordingDecisionLogStore(),
        clock,
        event_service=events,
    )

    asyncio.run(service.step())

    types = {event.event_type for event in events.list(agent_id=agent.id)}
    assert AgentEventType.NEED_CHANGED in types
    assert AgentEventType.GOAL_CHANGED in types
    assert AgentEventType.STATE_CHANGED in types
    thirst = [e for e in events.list(agent_id=agent.id) if e.event_type is AgentEventType.STATE_CHANGED]
    assert any("Thirst" in event.message for event in thirst)
# --- Planner generates decision/plan events --------------------------------


class FakeWorldRepository:
    """Minimal world repo double for the executor's move step."""

    def __init__(self, river_id: UUID) -> None:
        self._river_id = river_id
        self.locations: dict[UUID, UUID] = {}

    def set_agent_location(self, agent_id: UUID, location_id: UUID) -> None:
        self.locations[agent_id] = location_id

    def list_resources(self, location_id: UUID) -> list:
        """Minimal resource listing for drink/eat checks."""
        return []


class FakeContextBuilder:
    def __init__(self, context: DecisionContext) -> None:
        self._context = context

    def build(self, agent: object, *, tick: int, simulation_datetime: datetime, needs: object) -> DecisionContext:
        return self._context.model_copy(deep=True)


def test_planner_emits_decision_and_plan_events(tmp_path) -> None:
    river = Location(id=uuid4(), name="River")
    home = Location(id=uuid4(), name="Home")
    context = _context(home, river)
    events = _event_service(tmp_path)

    planner = CompositePlanner(
        planner_type="llm",
        rule_based_planner=RuleBasedPlanner(),
        llm_planner=LLMPlanner(provider=FakeLLMProvider(VALID_LLM_PLAN, model="fake-llm")),
        fallback_to_rules=True,
        validator=PlanValidator(),
    )
    brain = BrainService(
        context_builder=FakeContextBuilder(context),
        planner=planner,
        executor=PlanExecutor(FakeWorldRepository(river.id), event_service=events),
        store=BrainStateStore(),
        event_service=events,
    )

    agent = Agent(
        id=context.agent_id,
        name="Alice",
        needs=AgentNeeds(thirst=95),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=None,
    )
    outcome = brain.process_agent(
        agent,
        AgentNeeds(thirst=97),
        tick=1,
        simulation_datetime=datetime(2024, 1, 1, tzinfo=UTC),
    )

    recorded = events.list(agent_id=agent.id)
    types = [event.event_type for event in recorded]
    assert AgentEventType.DECISION in types
    assert AgentEventType.PLAN_CREATED in types
    assert AgentEventType.ACTION_COMPLETED in types
    assert outcome.action == "move"

    decision = next(event for event in recorded if event.event_type is AgentEventType.DECISION)
    assert decision.metadata["planner"] == "llm"
    plan = next(event for event in recorded if event.event_type is AgentEventType.PLAN_CREATED)
    assert "move → River" in plan.message and "drink → River" in plan.message
    action = next(event for event in recorded if event.event_type is AgentEventType.ACTION_COMPLETED)
    assert "Moved" in action.message and "River" in action.message
# --- Planner emits fallback event ------------------------------------------


def test_planner_emits_fallback_event(tmp_path) -> None:
    river = Location(id=uuid4(), name="River")
    home = Location(id=uuid4(), name="Home")
    context = _context(home, river)
    events = _event_service(tmp_path)

    planner = CompositePlanner(
        planner_type="llm",
        rule_based_planner=RuleBasedPlanner(),
        llm_planner=LLMPlanner(provider=FakeLLMProvider("this is not json", model="fake-llm")),
        fallback_to_rules=True,
        validator=PlanValidator(),
    )
    brain = BrainService(
        context_builder=FakeContextBuilder(context),
        planner=planner,
        executor=PlanExecutor(FakeWorldRepository(river.id), event_service=events),
        store=BrainStateStore(),
        event_service=events,
    )
    agent = Agent(
        id=context.agent_id,
        name="Alice",
        needs=AgentNeeds(thirst=95),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=None,
    )

    brain.process_agent(
        agent,
        AgentNeeds(thirst=97),
        tick=1,
        simulation_datetime=datetime(2024, 1, 1, tzinfo=UTC),
    )

    fallbacks = [e for e in events.list(agent_id=agent.id) if e.event_type is AgentEventType.FALLBACK]
    assert fallbacks
    assert "RuleBasedPlanner" in fallbacks[0].message


# --- Executor generates action events --------------------------------------


def test_executor_emits_action_event(tmp_path) -> None:
    river = Location(id=uuid4(), name="River")
    home = Location(id=uuid4(), name="Home")
    context = _context(home, river)
    events = _event_service(tmp_path)
    agent_id = context.agent_id

    executor = PlanExecutor(FakeWorldRepository(river.id), event_service=events)
    needs = AgentNeeds(thirst=97)
    from app.modules.cognition.action_plan import ActionPlanStep

    executor.execute_step(
        ActionPlanStep(action="drink", target="River", parameters={}),
        agent_id=agent_id,
        needs=needs,
        context=context,
        tick=2,
    )

    recorded = [e for e in events.list(agent_id=agent_id) if e.event_type is AgentEventType.ACTION_COMPLETED]
    assert len(recorded) == 1
    assert "Drank water at River" in recorded[0].message
    assert recorded[0].tick == 2
    assert needs.thirst == 27


# --- Memory generates memory events ----------------------------------------


@dataclass
class InMemoryMemoryRepository:
    saved_memories: list[Memory] = field(default_factory=list)

    def save(self, memory: Memory) -> Memory:
        self.saved_memories.append(memory)
        return memory


def test_memory_service_emits_memory_created_event(tmp_path) -> None:
    events = _event_service(tmp_path)
    memory_service = MemoryService(
        InMemoryMemoryRepository(),
        InMemoryEventBus(),
        event_service=events,
    )
    agent_id = uuid4()

    memory_service.record(
        CreateMemoryRequest(
            agent_id=agent_id,
            memory_type=MemoryType.EPISODIC,
            content="I found water at the river.",
            tick=2,
            event_type="drink",
        )
    )

    created = [e for e in events.list(agent_id=agent_id) if e.event_type is AgentEventType.MEMORY_CREATED]
    assert len(created) == 1
    assert created[0].message == "I found water at the river."
    assert created[0].tick == 2


def test_working_memory_does_not_flood_timeline(tmp_path) -> None:
    events = _event_service(tmp_path)
    memory_service = MemoryService(
        InMemoryMemoryRepository(),
        InMemoryEventBus(),
        event_service=events,
    )
    agent_id = uuid4()

    memory_service.record(
        CreateMemoryRequest(
            agent_id=agent_id,
            memory_type=MemoryType.WORKING,
            content="Current thought: drink/drink",
        )
    )

    assert events.list(agent_id=agent_id) == []
# --- HTTP API --------------------------------------------------------------


def test_agent_events_endpoint_returns_timeline(client) -> None:
    created = client.post("/api/v1/agents", json={"name": "Alice"}).json()
    agent_id = created["id"]

    first = client.get(f"/api/v1/agents/{agent_id}/events")
    assert first.status_code == 200
    assert first.json() == []

    # Event recording through the process-local service is visible to the API.
    from app.api import dependencies

    dependencies.get_agent_event_service().record(
        agent_id=UUID(agent_id),
        tick=1,
        event_type=AgentEventType.GOAL_CHANGED,
        message="Goal set: drink",
    )
    second = client.get(f"/api/v1/agents/{agent_id}/events?limit=10&offset=0")
    assert second.status_code == 200
    body = second.json()
    assert len(body) == 1
    assert body[0]["agent_id"] == agent_id
    assert body[0]["event_type"] == "goal_changed"
    assert body[0]["message"] == "Goal set: drink"
    assert "timestamp" in body[0]
    assert body[0]["tick"] == 1


# --- Event store / service unit tests -----------------------------------------


def test_record_returns_a_stored_event_with_required_fields(tmp_path) -> None:
    """A recorded event exposes every field required by the timeline model."""
    events = _event_service(tmp_path)
    agent_id = uuid4()

    event = events.record(
        agent_id=agent_id,
        tick=1,
        event_type=AgentEventType.NEED_CHANGED,
        message="Thirst 80 → 85",
        metadata={"need": "thirst", "before": 80, "after": 85},
    )

    assert event.id is not None
    assert str(event.agent_id) == str(agent_id)
    assert event.tick == 1
    assert event.event_type is AgentEventType.NEED_CHANGED
    assert event.message == "Thirst 80 → 85"
    assert event.timestamp is not None
    assert event.metadata == {"need": "thirst", "before": 80, "after": 85}


def test_events_persist_across_repository_reopen(tmp_path) -> None:
    """Events survive closing and reopening the SQLite backing store."""
    database_path = tmp_path / "events.sqlite"
    repository = SqliteAgentEventRepository(database_path)
    repository.initialize()
    service = AgentEventService(repository)
    agent_id = uuid4()

    service.record(
        agent_id=agent_id,
        tick=1,
        event_type=AgentEventType.GOAL_CHANGED,
        message="Goal set: drink",
    )

    reopened_repository = SqliteAgentEventRepository(database_path)
    reopened_repository.initialize()
    reopened_service = AgentEventService(reopened_repository)
    loaded = reopened_service.list(agent_id=agent_id)

    assert len(loaded) == 1
    assert loaded[0].event_type is AgentEventType.GOAL_CHANGED
    assert loaded[0].message == "Goal set: drink"
    assert str(loaded[0].agent_id) == str(agent_id)


def test_list_returns_events_ordered_oldest_first(tmp_path) -> None:
    """The timeline reads oldest → newest, matching dashboard display order."""
    events = _event_service(tmp_path)
    agent_id = uuid4()
    events.record(agent_id=agent_id, tick=1, event_type=AgentEventType.NEED_CHANGED, message="first")
    events.record(agent_id=agent_id, tick=2, event_type=AgentEventType.ACTION_COMPLETED, message="second")
    events.record(agent_id=agent_id, tick=3, event_type=AgentEventType.MEMORY_CREATED, message="third")

    listed = events.list(agent_id=agent_id)

    assert [event.message for event in listed] == ["first", "second", "third"]
    assert [event.tick for event in listed] == [1, 2, 3]


def test_list_filters_events_by_agent_id(tmp_path) -> None:
    """Querying for one agent never leaks another agent's events."""
    events = _event_service(tmp_path)
    alice = uuid4()
    bob = uuid4()
    events.record(agent_id=alice, tick=1, event_type=AgentEventType.NEED_CHANGED, message="Alice")
    events.record(agent_id=bob, tick=1, event_type=AgentEventType.NEED_CHANGED, message="Bob")
    events.record(agent_id=alice, tick=2, event_type=AgentEventType.STATE_CHANGED, message="Alice 2")

    alice_events = events.list(agent_id=alice)
    assert len(alice_events) == 2
    assert [event.message for event in alice_events] == ["Alice", "Alice 2"]
    assert all(event.agent_id == alice for event in alice_events)

    assert len(events.list(agent_id=bob)) == 1


def test_list_supports_limit_and_offset(tmp_path) -> None:
    """Pagination pages from newest events and returns each page oldest-first."""
    events = _event_service(tmp_path)
    agent_id = uuid4()
    for index in range(5):
        events.record(
            agent_id=agent_id,
            tick=index,
            event_type=AgentEventType.NEED_CHANGED,
            message=f"event {index}",
        )

    newest_two = events.list(agent_id=agent_id, limit=2, offset=0)
    assert [event.tick for event in newest_two] == [3, 4]

    older_two = events.list(agent_id=agent_id, limit=2, offset=2)
    assert [event.tick for event in older_two] == [1, 2]

    all_events = events.list(agent_id=agent_id, limit=100, offset=0)
    assert [event.tick for event in all_events] == [0, 1, 2, 3, 4]
