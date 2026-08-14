"""Tests for V0.8 reflection, semantic knowledge, and episode integration."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.core.events import InMemoryEventBus
from app.core.llm.fake import FakeLLMProvider
from app.modules.activity.models import AgentEventType
from app.modules.activity.repository import SqliteAgentEventRepository
from app.modules.activity.service import AgentEventService
from app.modules.agent.models import CreateAgentRequest
from app.modules.agent.repository import AgentRepository
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.brain_service import BrainService
from app.modules.cognition.brain_state import BrainStateStore
from app.modules.cognition.context_builder import ContextBuilder
from app.modules.cognition.plan_executor import PlanExecutor
from app.modules.cognition.plan_validator import PlanValidator
from app.modules.cognition.planner import RuleBasedPlanner
from app.modules.cognition.planner_service import CompositePlanner
from app.modules.cognition.reflection import EpisodeAction, EpisodeRecord, ReflectionEngine
from app.modules.memory.models import MemoryType
from app.modules.memory.repository import SqliteMemoryRepository
from app.modules.memory.service import MemoryService
from app.modules.simulation.service import SimulationService
from app.modules.world.clock import SimulationClock
from app.modules.world.repository import SqliteWorldRepository
from app.modules.world.service import WorldKnowledgeService, WorldPerceptionService
from app.modules.agent.logs import SqliteDecisionLogRepository


def test_reflection_engine_falls_back_when_llm_output_is_invalid() -> None:
    engine = ReflectionEngine(provider=FakeLLMProvider(response="not-json"))
    episode = EpisodeRecord(
        agent_id=uuid4(),
        agent_name="Alice",
        start_tick=1,
        end_tick=2,
        started_at=datetime(2024, 1, 1, tzinfo=UTC),
        ended_at=datetime(2024, 1, 1, tzinfo=UTC),
        goal="drink",
        planner="llm",
        initial_needs=AgentNeeds(thirst=95),
        final_needs=AgentNeeds(thirst=25),
        actions=[EpisodeAction(action="move", target="River"), EpisodeAction(action="drink", target="River")],
        summary="Alice reduced thirst by drinking at the river.",
        success=True,
    )

    result = engine.reflect(episode)

    assert result.source == "heuristic"
    assert result.error is not None
    assert result.output.knowledge
    assert result.output.knowledge[0].subject == "River"


def test_semantic_knowledge_is_deduplicated_and_strengthened(tmp_path) -> None:
    repository = SqliteMemoryRepository(tmp_path / "memory.sqlite")
    repository.initialize()
    service = MemoryService(repository, InMemoryEventBus())
    agent_id = uuid4()
    observed_at = datetime(2024, 1, 1, 10, 0, tzinfo=UTC)

    first = service.upsert_semantic_knowledge(
        agent_id=agent_id,
        subject="River",
        predicate="provides",
        object_value="drinkable water",
        confidence=0.6,
        observed_at=observed_at,
        lesson="The river satisfied thirst.",
    )
    second = service.upsert_semantic_knowledge(
        agent_id=agent_id,
        subject="River",
        predicate="provides",
        object_value="drinkable water",
        confidence=0.62,
        observed_at=observed_at + timedelta(minutes=5),
        lesson="The same strategy worked again.",
    )

    assert first.id == second.id
    memories = service.list_memories(agent_id=agent_id, limit=10)
    semantic = [memory for memory in memories if memory.memory_type is MemoryType.SEMANTIC]
    assert len(semantic) == 1
    assert semantic[0].metadata["times_observed"] == 2
    assert float(semantic[0].metadata["confidence"]) > 0.62


def test_completed_episode_triggers_reflection_and_knowledge_event(tmp_path) -> None:
    world_repo = SqliteWorldRepository(tmp_path / "world.sqlite")
    world_repo.initialize()
    home = world_repo.create_location("Home", "A safe house")
    river = world_repo.create_location("River", "A flowing river")
    world_repo.connect_locations(home.id, river.id)
    world_repo.create_entity("Water", river.id, {"drinkable": True})

    agent_repo = AgentRepository(tmp_path / "agents.sqlite")
    agent_repo.initialize()
    agent = agent_repo.create(CreateAgentRequest(name="Alice", needs=AgentNeeds(thirst=95)))
    world_repo.set_agent_location(agent.id, home.id)

    event_repo = SqliteAgentEventRepository(tmp_path / "events.sqlite")
    event_repo.initialize()
    event_service = AgentEventService(event_repo)

    memory_repo = SqliteMemoryRepository(tmp_path / "memory.sqlite")
    memory_repo.initialize()
    memory_service = MemoryService(memory_repo, InMemoryEventBus(), event_service=event_service)

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
        executor=PlanExecutor(world_repo, event_service=event_service),
        store=BrainStateStore(),
        event_service=event_service,
    )

    log_repo = SqliteDecisionLogRepository(tmp_path / "logs.sqlite")
    log_repo.initialize()
    service = SimulationService(
        agent_repo,
        log_repo,
        SimulationClock(datetime(2024, 1, 1, tzinfo=UTC), tick_duration=timedelta(minutes=1)),
        memory_service=memory_service,
        brain=brain,
        reflection_engine=ReflectionEngine(provider=None),
        event_service=event_service,
    )

    import asyncio

    async def run_two_ticks() -> None:
        await service.step()
        await service.step()

    asyncio.run(run_two_ticks())

    events = event_service.list(agent_id=agent.id, limit=200)
    event_types = [event.event_type for event in events]
    assert AgentEventType.REFLECTION in event_types
    assert AgentEventType.KNOWLEDGE in event_types

    semantic = [memory for memory in memory_service.list_memories(agent_id=agent.id, limit=50) if memory.memory_type is MemoryType.SEMANTIC]
    assert semantic
    assert semantic[0].metadata.get("knowledge", {}).get("subject") == "River"
