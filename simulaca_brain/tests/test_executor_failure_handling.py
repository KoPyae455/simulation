"""Regression tests for executor failures not crashing the simulation step."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import pytest

from app.core.llm.fake import FakeLLMProvider
from app.core.events import InMemoryEventBus
from app.modules.activity.repository import SqliteAgentEventRepository
from app.modules.activity.service import AgentEventService
from app.modules.agent.models import Agent
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.brain_service import BrainService
from app.modules.cognition.brain_state import BrainStateStore
from app.modules.cognition.context_builder import ContextBuilder
from app.modules.cognition.llm_planner import LLMPlanner
from app.modules.cognition.plan_executor import PlanExecutor
from app.modules.cognition.plan_validator import PlanValidator
from app.modules.cognition.planner import RuleBasedPlanner
from app.modules.cognition.planner_service import CompositePlanner
from app.modules.memory.repository import SqliteMemoryRepository
from app.modules.memory.service import MemoryService
from app.modules.simulation.service import SimulationService
from app.modules.world.models import Location
from app.modules.world.repository import SqliteWorldRepository
from app.modules.world.service import WorldKnowledgeService, WorldPerceptionService
from app.modules.world.clock import SimulationClock
from datetime import timedelta


class RecordingAgentStore:
    def __init__(self, agent):
        self._agent = agent

    def list(self, limit, offset):
        return [self._agent]

    def update(self, agent_id, request):
        self._agent = Agent(
            id=self._agent.id,
            name=getattr(request, 'name', None) or self._agent.name,
            needs=getattr(request, 'needs', None) or self._agent.needs,
            created_at=self._agent.created_at,
            updated_at=self._agent.updated_at,
        )
        return self._agent


class RecordingDecisionLogStore:
    def __init__(self):
        self.logs = []

    def save(self, log):
        self.logs.append(log)
        return log

    def list(self, agent_id=None, limit=50):
        return self.logs


def _build_world(tmp_path):
    repo = SqliteWorldRepository(tmp_path / "world.db")
    repo.initialize()
    home = repo.create_location("Home", "Alice's house")
    river = repo.create_location("River", "A river with drinkable water")
    repo.connect_locations(home.id, river.id)
    return repo, home, river


def _build_service(tmp_path, agent, llm_response, planner_type="llm"):
    world_repo, home, river = _build_world(tmp_path)
    world_repo.set_agent_location(agent.id, home.id)

    world_knowledge = WorldKnowledgeService(world_repo)
    world_perception = WorldPerceptionService(world_knowledge, world_repo)

    memory_repo = SqliteMemoryRepository(tmp_path / "memory.db")
    memory_repo.initialize()
    event_repo = SqliteAgentEventRepository(tmp_path / "events.db")
    event_repo.initialize()
    event_service = AgentEventService(event_repo)

    memory_service = MemoryService(memory_repo, InMemoryEventBus(), event_service=event_service)

    fake_llm = FakeLLMProvider(response=llm_response)
    store = BrainStateStore()
    validator = PlanValidator()
    context_builder = ContextBuilder(
        perception=world_perception,
        world_repository=world_repo,
        memory_service=memory_service,
    )
    llm_planner = LLMPlanner(provider=fake_llm, validator=validator)
    rule_based_planner = RuleBasedPlanner()
    composite_planner = CompositePlanner(
        planner_type=planner_type,
        rule_based_planner=rule_based_planner,
        llm_planner=llm_planner,
        fallback_to_rules=True,
        validator=validator,
    )
    executor = PlanExecutor(world_repo, event_service=event_service)
    brain = BrainService(
        context_builder=context_builder,
        planner=composite_planner,
        executor=executor,
        store=store,
        event_service=event_service,
    )

    agents = RecordingAgentStore(agent)
    logs = RecordingDecisionLogStore()
    clock = SimulationClock(datetime(2024, 1, 1, tzinfo=UTC), tick_duration=timedelta(minutes=1))

    service = SimulationService(
        agents=agents,
        logs=logs,
        clock=clock,
        memory_service=memory_service,
        brain=brain,
        event_service=event_service,
    )
    return service, agents, logs, event_service


def test_valid_llm_plan_executes_without_error():
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        agent = Agent(
            id=uuid4(),
            name="Alice",
            needs=AgentNeeds(hunger=40, thirst=82, fatigue=40, safety=50, comfort=50, social=40),
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

        llm_response = json.dumps({
            "goal": "drink",
            "reasoning_summary": "Alice is thirsty.",
            "steps": [
                {"action": "move", "target": "River"},
                {"action": "drink", "target": "River"}
            ]
        })

        service, agents, logs, event_service = _build_service(tmp_path, agent, llm_response)
        result = asyncio.run(service.step())
        assert result.current_tick == 1
        assert result.agents_updated == 1
        assert agents._agent.needs.thirst == 84  # 82 + 2 decay


def test_unmappable_llm_action_triggers_fallback_not_crash():
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        agent = Agent(
            id=uuid4(),
            name="Alice",
            needs=AgentNeeds(hunger=40, thirst=82, fatigue=40, safety=50, comfort=50, social=40),
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

        # "teleport" is not in any alias map, so it cannot be normalized and
        # must be rejected by the validator -> rule-based fallback (not crash).
        llm_response = json.dumps({
            "goal": "drink",
            "reasoning_summary": "Alice should appear at the river.",
            "steps": [
                {"action": "teleport", "target": "River"}
            ]
        })

        service, agents, logs, event_service = _build_service(tmp_path, agent, llm_response)
        result = asyncio.run(service.step())
        assert result.current_tick == 1
        assert result.agents_updated == 1

        events = event_service.list(agent_id=agent.id)
        event_types = [e.event_type for e in events]
        from app.modules.activity.models import AgentEventType
        assert AgentEventType.FALLBACK in event_types
        assert AgentEventType.ACTION_COMPLETED in event_types


def test_normalizable_llm_action_is_used_without_fallback():
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        agent = Agent(
            id=uuid4(),
            name="Alice",
            needs=AgentNeeds(hunger=40, thirst=82, fatigue=40, safety=50, comfort=50, social=40),
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

        # "go to river" (human-readable) is normalized to canonical "move".
        llm_response = json.dumps({
            "goal": "thirst",  # also normalized to "drink"
            "reasoning_summary": "Alice should go to river and drink.",
            "steps": [
                {"action": "go to river", "target": "River"},
                {"action": "drink water", "target": "River"}
            ]
        })

        service, agents, logs, event_service = _build_service(tmp_path, agent, llm_response)
        result = asyncio.run(service.step())
        assert result.current_tick == 1
        assert result.agents_updated == 1

        events = event_service.list(agent_id=agent.id)
        event_types = [e.event_type for e in events]
        from app.modules.activity.models import AgentEventType
        # Normalized actions are valid, so no fallback event is emitted.
        assert AgentEventType.FALLBACK not in event_types
        assert AgentEventType.PLAN_CREATED in event_types
        assert AgentEventType.ACTION_COMPLETED in event_types


def test_executor_failure_emits_error_event_and_continues():
    with TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        agent = Agent(
            id=uuid4(),
            name="Alice",
            needs=AgentNeeds(hunger=40, thirst=82, fatigue=40, safety=50, comfort=50, social=40),
            created_at=datetime(2024, 1, 1, tzinfo=UTC),
            updated_at=datetime(2024, 1, 1, tzinfo=UTC),
        )

        llm_response = json.dumps({
            "goal": "drink",
            "reasoning_summary": "Alice is thirsty.",
            "steps": [
                {"action": "move", "target": "NonexistentPlace"}
            ]
        })

        service, agents, logs, event_service = _build_service(tmp_path, agent, llm_response)
        result = asyncio.run(service.step())
        assert result.current_tick == 1
        assert result.agents_updated == 1

        events = event_service.list(agent_id=agent.id)
        event_types = [e.event_type for e in events]
        from app.modules.activity.models import AgentEventType
        # Invalid LLM target triggers fallback to rules, not a crash
        assert AgentEventType.FALLBACK in event_types
        assert AgentEventType.ACTION_COMPLETED in event_types
