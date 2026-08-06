"""Unit tests for deterministic agent life-cycle behavior."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.agent.logs import AgentDecisionLog
from app.modules.agent.models import Agent, UpdateAgentRequest
from app.modules.agent.state import AgentNeeds
from app.modules.simulation.service import SimulationService
from app.modules.world.clock import SimulationClock


class RecordingAgentStore:
    """In-memory test double for persisted agent state."""

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
    """In-memory test double for persisted decision logs."""

    def __init__(self) -> None:
        self.logs: list[AgentDecisionLog] = []

    def save(self, log: AgentDecisionLog) -> AgentDecisionLog:
        self.logs.append(log)
        return log

    def list(self, agent_id: object | None, limit: int) -> list[AgentDecisionLog]:
        return self.logs

    def clear(self) -> None:
        self.logs.clear()


def _build_service() -> tuple[SimulationService, RecordingAgentStore, RecordingDecisionLogStore]:
    agent = Agent(
        id=uuid4(),
        name="Alice",
        needs=AgentNeeds(hunger=90, thirst=85, fatigue=95, safety=20, comfort=15, social=20),
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    agents = RecordingAgentStore(agent)
    logs = RecordingDecisionLogStore()
    clock = SimulationClock(datetime(2024, 1, 1, tzinfo=UTC), tick_duration=timedelta(minutes=1))
    return SimulationService(agents, logs, clock), agents, logs


def test_need_updates_follow_the_deterministic_rule_set() -> None:
    service, _, _ = _build_service()

    updated_needs = service._advance_needs(AgentNeeds(hunger=98, thirst=90, fatigue=98, safety=30, comfort=10, social=20))

    assert updated_needs.hunger == 99
    assert updated_needs.thirst == 92
    assert updated_needs.fatigue == 99
    assert updated_needs.comfort == 10
    assert updated_needs.social == 21


def test_goal_generation_prefers_the_requested_priority_order() -> None:
    service, _, _ = _build_service()

    assert service._generate_goal(AgentNeeds(thirst=81)) == "drink"
    assert service._generate_goal(AgentNeeds(hunger=81)) == "eat"
    assert service._generate_goal(AgentNeeds(fatigue=81)) == "sleep"
    assert service._generate_goal(AgentNeeds()) == "idle"


def test_actions_modify_internal_state_and_clamp_values() -> None:
    service, _, _ = _build_service()

    needs = AgentNeeds(hunger=50, thirst=40, fatigue=50, safety=20, comfort=10, social=20)

    service._execute_action(needs, "eat")
    assert needs.hunger == 0
    assert needs.thirst == 40

    service._execute_action(needs, "drink")
    assert needs.thirst == 0

    service._execute_action(needs, "sleep")
    assert needs.fatigue == 0


def test_step_advances_clock_and_emits_a_decision_log() -> None:
    service, _, logs = _build_service()

    result = asyncio.run(service.step())

    assert result.current_tick == 1
    assert result.agents_updated == 1
    assert len(logs.logs) == 1
    assert logs.logs[0].action in {"eat", "drink", "sleep", "idle"}
