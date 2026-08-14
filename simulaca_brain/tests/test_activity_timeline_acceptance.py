"""End-to-end acceptance test for the V0.7.1 agent activity timeline.

Scenario: Alice starts at Home with critical thirst (95). The world links
Home <-> River, and the River has drinkable water. Two simulation ticks walk
her to the River and let her drink, reducing thirst. Every observable step
must appear in the agent timeline, in order.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from app.core.events import InMemoryEventBus
from app.modules.activity.models import AgentEventType
from app.modules.activity.repository import SqliteAgentEventRepository
from app.modules.activity.service import AgentEventService
from app.modules.agent.logs import SqliteDecisionLogRepository
from app.modules.agent.models import CreateAgentRequest
from app.modules.agent.repository import AgentRepository
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.brain_service import BrainService
from app.modules.cognition.brain_state import BrainStateStore
from app.modules.cognition.context_builder import ContextBuilder
from app.modules.cognition.plan_executor import PlanExecutor
from app.modules.cognition.planner import RuleBasedPlanner
from app.modules.cognition.planner_service import CompositePlanner
from app.modules.cognition.plan_validator import PlanValidator
from app.modules.memory.repository import SqliteMemoryRepository
from app.modules.memory.service import MemoryService
from app.modules.simulation.service import SimulationService
from app.modules.world.clock import SimulationClock
from app.modules.world.repository import SqliteWorldRepository
from app.modules.world.service import WorldKnowledgeService, WorldPerceptionService


def test_acceptance_alice_drinks_at_river_timeline(tmp_path) -> None:
    """Alice walks from Home to the River and drinks, all visible on the timeline."""
    # --- World: Home <-> River with drinkable water at the River ---
    world_repo = SqliteWorldRepository(tmp_path / "world.sqlite")
    world_repo.initialize()
    home = world_repo.create_location("Home", "A cozy home.")
    river = world_repo.create_location("River", "A flowing river.")
    world_repo.connect_locations(home.id, river.id)
    world_repo.create_entity("Water", river.id, {"drinkable": True})

    # --- Agent: Alice at Home with critical thirst ---
    agent_repo = AgentRepository(tmp_path / "agents.sqlite")
    agent_repo.initialize()
    agent = agent_repo.create(CreateAgentRequest(name="Alice", needs=AgentNeeds(thirst=95)))
    world_repo.set_agent_location(agent.id, home.id)

    # --- Event store + memory ---
    event_repo = SqliteAgentEventRepository(tmp_path / "events.sqlite")
    event_repo.initialize()
    events = AgentEventService(event_repo)

    memory_repo = SqliteMemoryRepository(tmp_path / "memory.sqlite")
    memory_repo.initialize()
    memory_service = MemoryService(memory_repo, InMemoryEventBus(), event_service=events)

    # --- Brain: rule-based planner (no LLM required for this scenario) ---
    perception = WorldPerceptionService(WorldKnowledgeService(world_repo), world_repo)
    context_builder = ContextBuilder(perception, world_repo, memory_service)
    brain = BrainService(
        context_builder=context_builder,
        planner=CompositePlanner(
            planner_type="rules",
            rule_based_planner=RuleBasedPlanner(),
            llm_planner=None,
            fallback_to_rules=True,
            validator=PlanValidator(),
        ),
        executor=PlanExecutor(world_repo, event_service=events),
        store=BrainStateStore(),
        event_service=events,
    )

    # --- Simulation ---
    log_repo = SqliteDecisionLogRepository(tmp_path / "logs.sqlite")
    log_repo.initialize()
    clock = SimulationClock(datetime(2024, 1, 1, tzinfo=UTC), tick_duration=timedelta(minutes=1))
    service = SimulationService(
        agent_repo,
        log_repo,
        clock,
        memory_service=memory_service,
        brain=brain,
        event_service=events,
    )

    async def run_two_ticks() -> None:
        await service.step()  # tick 1 -> move Home -> River
        await service.step()  # tick 2 -> drink at River

    asyncio.run(run_two_ticks())

    timeline = events.list(agent_id=agent.id)
    types = {event.event_type for event in timeline}

    # Every meaningful observable category shows up at least once.
    for expected in (
        AgentEventType.NEED_CHANGED,
        AgentEventType.GOAL_CHANGED,
        AgentEventType.DECISION,
        AgentEventType.PLAN_CREATED,
        AgentEventType.ACTION_COMPLETED,
        AgentEventType.STATE_CHANGED,
        AgentEventType.MEMORY_CREATED,
    ):
        assert expected in types, f"missing {expected.value} event in timeline"

    # The generated plan moves to and drinks at the River.
    plan = next(event for event in timeline if event.event_type is AgentEventType.PLAN_CREATED)
    assert "move → River" in plan.message
    assert "drink → River" in plan.message

    # Tick 1 moves the agent to the River; tick 2 has her drink there.
    actions = [event for event in timeline if event.event_type is AgentEventType.ACTION_COMPLETED]
    assert len(actions) == 2
    assert "Moved Home → River" in actions[0].message
    assert "Drank water at River" in actions[1].message
    assert actions[0].tick == 1
    assert actions[1].tick == 2

    # Drinking resolved thirst: a state_changed event lowers it substantially.
    state_change = next(
        event for event in timeline if event.event_type is AgentEventType.STATE_CHANGED
    )
    assert state_change.metadata["need"] == "thirst"
    assert state_change.metadata["before"] > state_change.metadata["after"]
    assert state_change.metadata["before"] - state_change.metadata["after"] >= 60

    # Ordering: need change -> plan -> first action -> state change.
    need_index = next(i for i, event in enumerate(timeline) if event.event_type is AgentEventType.NEED_CHANGED)
    plan_index = next(i for i, event in enumerate(timeline) if event.event_type is AgentEventType.PLAN_CREATED)
    action_index = next(i for i, event in enumerate(timeline) if event.event_type is AgentEventType.ACTION_COMPLETED)
    state_index = next(i for i, event in enumerate(timeline) if event.event_type is AgentEventType.STATE_CHANGED)
    assert need_index < plan_index < action_index < state_index

    # The agent physically ended up at the River.
    assert world_repo.get_agent_location(agent.id) == river.id
