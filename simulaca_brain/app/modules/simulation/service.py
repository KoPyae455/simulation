"""Application service that advances agent state through simulation ticks."""

import asyncio
import math
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from app.modules.agent.logs import AgentDecisionLog, DecisionLogStore
from app.modules.agent.models import Agent, UpdateAgentRequest
from app.modules.agent.repository import AgentRepository
from app.modules.agent.state import AgentNeeds, NeedType
from app.modules.memory.models import CreateMemoryRequest, MemoryType
from app.modules.memory.service import MemoryService
from app.modules.cognition.brain_service import BrainService
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

    def __init__(
        self,
        agents: AgentStateStore,
        logs: DecisionLogStore,
        clock: SimulationClock,
        memory_service: MemoryService | None = None,
        brain: BrainService | None = None,
    ) -> None:
        """Create a simulation coordinator with injected state, log, and memory dependencies."""
        self._agents = agents
        self._logs = logs
        self._clock = clock
        self._memory_service = memory_service
        self._brain = brain
        self._control_lock = asyncio.Lock()
        self._auto_run_task: asyncio.Task[None] | None = None
        self._last_goal: str | None = None
        self._last_action: str | None = None

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
            current_goal=self._last_goal,
            current_action=self._last_action,
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
            if self._brain is not None:
                goal, action, action_target, final_needs, reason = self._cognize(agent, updated_needs, tick)
            else:
                goal = self._generate_goal(updated_needs)
                action = self._resolve_action(goal)
                self._execute_action(updated_needs, action)
                final_needs = updated_needs
                action_target = None
                reason = self._reason_for(goal, final_needs)

            updated_agent = self._agents.update(agent.id, UpdateAgentRequest(needs=final_needs))
            self._logs.save(
                self._build_decision_log(
                    updated_agent,
                    tick.simulation_datetime,
                    goal=goal,
                    action=action or "idle",
                    reason=reason,
                )
            )
            self._last_goal = goal
            self._last_action = action
            if self._memory_service is not None:
                self._memory_service.set_working_memory(
                    agent.id,
                    current_goal=goal,
                    current_action=action or "idle",
                    target=action_target or agent.name,
                    started_at=tick.simulation_datetime,
                )
                self._memory_service.record(
                    CreateMemoryRequest(
                        agent_id=agent.id,
                        memory_type=MemoryType.EPISODIC,
                        content=f"{agent.name} performed {action or 'idle'}.",
                        tick=tick.number,
                        timestamp=tick.simulation_datetime,
                        event_type=action or "idle",
                        description=f"{agent.name} {action or 'idle'}ed.",
                        location=action_target or agent.name,
                        result=f"{goal} resolved",
                        importance=0.3,
                        metadata={"goal": goal, "action": action or "idle"},
                    )
                )
            agents_updated += 1

        return SimulationStepResult(
            current_tick=tick.number,
            current_simulation_datetime=tick.simulation_datetime,
            is_running=self.status.is_running,
            current_goal=self._last_goal,
            current_action=self._last_action,
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

    def _cognize(
        self,
        agent: Agent,
        needs: AgentNeeds,
        tick,
    ) -> tuple[str, str | None, str | None, AgentNeeds, str]:
        """Run the cognitive pipeline for ``agent`` and execute one step.

        Returns ``(goal, action, action_target, final_needs, reason)``.
        The LLM never mutates agent state; the BrainService validates the
        plan and executes exactly one step via the PlanExecutor.
        """
        assert self._brain is not None
        outcome = self._brain.process_agent(
            agent,
            needs,
            tick=tick.number,
            simulation_datetime=tick.simulation_datetime,
        )
        return (
            outcome.goal,
            outcome.action,
            outcome.target,
            outcome.needs,
            outcome.reason,
        )

    def _advance_needs(self, needs: AgentNeeds) -> AgentNeeds:
        """Return a copied needs state after applying one tick's rule-based urgency updates."""
        updated_needs = needs.model_copy(deep=True)
        updated_needs.hunger = self._clamp(updated_needs.hunger + 1)
        updated_needs.thirst = self._clamp(updated_needs.thirst + 2)
        updated_needs.fatigue = self._clamp(updated_needs.fatigue + 1)
        updated_needs.safety = self._clamp(updated_needs.safety + 0)
        updated_needs.comfort = self._clamp(updated_needs.comfort + 0)
        updated_needs.social = self._clamp(int(math.ceil(updated_needs.social + 0.2)))
        return updated_needs

    def _generate_goal(self, needs: AgentNeeds) -> str:
        """Return the single deterministic goal that best matches the current need priorities."""
        if needs.thirst > 80:
            return "drink"
        if needs.hunger > 80:
            return "eat"
        if needs.fatigue > 80:
            return "sleep"
        return "idle"

    def _resolve_action(self, goal: str) -> str:
        """Map a goal to the required deterministic action."""
        return {
            "drink": "drink",
            "eat": "eat",
            "sleep": "sleep",
            "idle": "idle",
        }.get(goal, "idle")

    def _execute_action(self, needs: AgentNeeds, action: str) -> None:
        """Apply the chosen action directly to the agent's internal needs."""
        if action == "eat":
            needs.hunger = self._clamp(needs.hunger - 60)
        elif action == "drink":
            needs.thirst = self._clamp(needs.thirst - 70)
        elif action == "sleep":
            needs.fatigue = self._clamp(needs.fatigue - 80)

    @staticmethod
    def _reason_for(goal: str, needs: AgentNeeds) -> str:
        if goal == "drink":
            return f"Thirst exceeded threshold at {needs.thirst}/100."
        if goal == "eat":
            return f"Hunger exceeded threshold at {needs.hunger}/100."
        if goal == "sleep":
            return f"Fatigue exceeded threshold at {needs.fatigue}/100."
        return "No critical need exceeded the threshold."

    @staticmethod
    def _build_decision_log(
        agent: Agent,
        timestamp: datetime,
        *,
        goal: str,
        action: str,
        reason: str,
    ) -> AgentDecisionLog:
        """Create a deterministic decision log from the completed rule pipeline."""
        return AgentDecisionLog(
            id=uuid4(),
            timestamp=timestamp,
            agent_id=agent.id,
            agent_name=agent.name,
            action=action,
            reason=f"Goal={goal}; {reason}",
            internal_state_snapshot=agent.needs.model_copy(deep=True),
        )

    @staticmethod
    def _clamp(value: int) -> int:
        return max(0, min(100, value))


def create_default_simulation_service(
    agents: AgentRepository,
    logs: DecisionLogStore,
    memory_service: MemoryService | None = None,
    brain: BrainService | None = None,
) -> SimulationService:
    """Build the process-local simulation service using the default world clock settings."""
    return SimulationService(
        agents=agents,
        logs=logs,
        clock=SimulationClock(start_datetime=datetime.now(UTC)),
        memory_service=memory_service,
        brain=brain,
    )
