"""Application service that advances agent state through simulation ticks."""

import asyncio
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from app.modules.agent.logs import AgentDecisionLog, DecisionLogStore
from app.modules.agent.models import Agent, UpdateAgentRequest
from app.modules.agent.repository import AgentRepository
from app.modules.agent.state import AgentNeeds, NeedType
from app.modules.simulation.models import SimulationStatus, SimulationStepResult
from app.modules.world.clock import SimulationClock


class AgentStateStore(Protocol):
    """Persistence port required to read and update agents during a tick."""

    def list(self, limit: int, offset: int) -> list[Agent]:
        """Return one bounded page of persisted agents."""

    def update(self, agent_id: object, request: UpdateAgentRequest) -> Agent:
        """Persist an agent update and return the new agent state."""


class SimulationService:
    """Coordinate ticking, deterministic need changes, logging, and auto-run lifecycle."""

    _PAGE_SIZE = 200
    _AUTO_STEP_INTERVAL = timedelta(seconds=2)
    _NEED_INCREMENTS: tuple[tuple[NeedType, int], ...] = (
        (NeedType.HUNGER, 5),
        (NeedType.THIRST, 4),
        (NeedType.FATIGUE, 3),
        (NeedType.SOCIAL, 1),
        (NeedType.SAFETY, 1),
        (NeedType.COMFORT, 2),
    )

    def __init__(self, agents: AgentStateStore, logs: DecisionLogStore, clock: SimulationClock) -> None:
        """Create a simulation coordinator with injected state and log dependencies."""
        self._agents = agents
        self._logs = logs
        self._clock = clock
        self._control_lock = asyncio.Lock()
        self._auto_run_task: asyncio.Task[None] | None = None

    async def step(self) -> SimulationStepResult:
        """Advance one tick and synchronously apply deterministic updates in a worker thread."""
        async with self._control_lock:
            return await asyncio.to_thread(self._step_synchronously)

    async def start(self) -> SimulationStatus:
        """Start automatic simulation ticks; repeated calls while running are idempotent."""
        async with self._control_lock:
            if self._auto_run_task is None or self._auto_run_task.done():
                self._auto_run_task = asyncio.create_task(self._run_automatically(), name="simulation-auto-run")
            return self.status

    async def stop(self) -> SimulationStatus:
        """Stop automatic ticking while preserving manual step capability."""
        async with self._control_lock:
            task = self._auto_run_task
            self._auto_run_task = None

        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        return self.status

    async def shutdown(self) -> None:
        """Stop background work during application shutdown."""
        await self.stop()

    @property
    def status(self) -> SimulationStatus:
        """Return the current clock and automatic-loop state."""
        task = self._auto_run_task
        return SimulationStatus(
            current_tick=self._clock.current_tick,
            current_simulation_datetime=self._clock.current_datetime,
            is_running=task is not None and not task.done(),
        )

    async def _run_automatically(self) -> None:
        """Run a periodic tick loop until cancellation is requested."""
        while True:
            await self.step()
            await asyncio.sleep(self._AUTO_STEP_INTERVAL.total_seconds())

    def _step_synchronously(self) -> SimulationStepResult:
        """Advance the clock and update all persisted agents in deterministic order."""
        tick = self._clock.tick()
        if tick is None:
            raise RuntimeError("The simulation clock is paused.")

        agents_updated = 0
        for agent in self._all_agents():
            updated_needs = self._advance_needs(agent.needs)
            updated_agent = self._agents.update(agent.id, UpdateAgentRequest(needs=updated_needs))
            self._logs.save(self._build_decision_log(updated_agent, tick.simulation_datetime))
            agents_updated += 1

        return SimulationStepResult(
            current_tick=tick.number,
            current_simulation_datetime=tick.simulation_datetime,
            is_running=self.status.is_running,
            agents_updated=agents_updated,
        )

    def _all_agents(self) -> Sequence[Agent]:
        """Load all persisted agents by walking repository pages."""
        agents: list[Agent] = []
        offset = 0
        while True:
            page = self._agents.list(self._PAGE_SIZE, offset)
            agents.extend(page)
            if len(page) < self._PAGE_SIZE:
                return agents
            offset += len(page)

    def _advance_needs(self, needs: AgentNeeds) -> AgentNeeds:
        """Return a copied needs state after applying one tick's urgency increments."""
        updated_needs = needs.model_copy(deep=True)
        for need, increment in self._NEED_INCREMENTS:
            updated_needs.increase(need, increment)
        return updated_needs

    @staticmethod
    def _build_decision_log(agent: Agent, timestamp: datetime) -> AgentDecisionLog:
        """Create a transparent rule-engine decision log from updated agent needs."""
        critical_actions: tuple[tuple[NeedType, str, str], ...] = (
            (NeedType.HUNGER, "EAT_FOOD", "Hunger reached"),
            (NeedType.THIRST, "DRINK_WATER", "Thirst reached"),
            (NeedType.FATIGUE, "REST", "Fatigue reached"),
            (NeedType.SOCIAL, "SEEK_SOCIAL_CONTACT", "Social need reached"),
            (NeedType.SAFETY, "SEEK_SAFETY", "Safety need reached"),
            (NeedType.COMFORT, "IMPROVE_COMFORT", "Comfort need reached"),
        )
        action, reason = "WAIT", "No critical need detected."
        for need, candidate_action, reason_prefix in critical_actions:
            value = agent.needs.get(need)
            if value >= 80:
                action = candidate_action
                reason = f"{reason_prefix} {value}/100."
                break

        return AgentDecisionLog(
            id=uuid4(),
            timestamp=timestamp,
            agent_id=agent.id,
            agent_name=agent.name,
            action=action,
            reason=reason,
            internal_state_snapshot=agent.needs.model_copy(deep=True),
        )


def create_default_simulation_service(agents: AgentRepository, logs: DecisionLogStore) -> SimulationService:
    """Build the process-local simulation service using the default world clock settings."""
    return SimulationService(
        agents=agents,
        logs=logs,
        clock=SimulationClock(start_datetime=datetime.now(UTC)),
    )
