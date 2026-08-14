"""Application service that advances agent state through simulation ticks."""

import asyncio
import math
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID, uuid4

from app.modules.activity.models import AgentEventType
from app.modules.activity.service import AgentEventService
from app.modules.agent.logs import AgentDecisionLog, DecisionLogStore
from app.modules.agent.models import Agent, UpdateAgentRequest
from app.modules.agent.repository import AgentRepository
from app.modules.agent.state import AgentNeeds, NeedType
from app.modules.memory.models import CreateMemoryRequest, MemoryType
from app.modules.memory.service import MemoryService
from app.modules.cognition.brain_service import AgentStepOutcome, BrainService
from app.modules.cognition.reflection import EpisodeAction, EpisodeRecord, ReflectionEngine
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
        reflection_engine: ReflectionEngine | None = None,
        event_service: AgentEventService | None = None,
    ) -> None:
        """Create a simulation coordinator with injected state, log, and memory dependencies."""
        self._agents = agents
        self._logs = logs
        self._clock = clock
        self._memory_service = memory_service
        self._brain = brain
        self._reflection_engine = reflection_engine
        self._event_service = event_service
        self._control_lock = asyncio.Lock()
        self._auto_run_task: asyncio.Task[None] | None = None
        self._last_goal: str | None = None
        self._last_action: str | None = None
        self._agent_last_goals: dict[UUID, str] = {}

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
        import logging as _logging
        _log = _logging.getLogger("simulaca.debug.simulation")
        tick = self._clock.tick()
        if tick is None:
            raise RuntimeError("The simulation clock is paused.")

        agents_updated = 0
        for agent in self._all_agents():
            pre_advance = agent.needs
            updated_needs = self._advance_needs(pre_advance)
            self._emit_need_changes(agent, pre_advance, updated_needs, tick)

            pre_action = updated_needs.model_copy(deep=True)
            step_outcome: AgentStepOutcome | None = None
            if self._brain is not None:
                try:
                    step_outcome = self._cognize(agent, updated_needs, tick)
                    goal = step_outcome.goal
                    action = step_outcome.action
                    action_target = step_outcome.target
                    final_needs = step_outcome.needs
                    reason = step_outcome.reason
                except Exception as exc:
                    _log.debug(
                        "SIM_COGNIZE_FAIL agent=%s tick=%s needs=%s error=%s error_type=%s",
                        agent.name,
                        tick.number,
                        updated_needs.model_dump(),
                        str(exc),
                        type(exc).__name__,
                    )
                    raise
            else:
                goal = self._generate_goal(updated_needs)
                action = self._resolve_action(goal)
                self._execute_action(updated_needs, action)
                final_needs = updated_needs
                action_target = None
                reason = self._reason_for(goal, final_needs)

            self._emit_goal_changed(agent, goal, tick)
            self._emit_state_changes(agent, pre_action, final_needs, action, tick)

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
                if step_outcome is not None:
                    self._reflect_completed_episode(
                        agent=agent,
                        outcome=step_outcome,
                        tick_number=tick.number,
                        tick_datetime=tick.simulation_datetime,
                        initial_needs=pre_action,
                        final_needs=final_needs,
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
    ) -> AgentStepOutcome:
        """Run the cognitive pipeline for ``agent`` and execute one step.
        """
        assert self._brain is not None
        return self._brain.process_agent(
            agent,
            needs,
            tick=tick.number,
            simulation_datetime=tick.simulation_datetime,
        )

    def _reflect_completed_episode(
        self,
        *,
        agent: Agent,
        outcome: AgentStepOutcome,
        tick_number: int,
        tick_datetime: datetime,
        initial_needs: AgentNeeds,
        final_needs: AgentNeeds,
    ) -> None:
        """Run one reflection pass after a meaningful completed episode."""
        if (
            self._reflection_engine is None
            or self._memory_service is None
            or not outcome.completed
            or outcome.decision.plan is None
        ):
            return

        actions = [
            EpisodeAction(action=step.action, target=step.target)
            for step in outcome.decision.plan.steps
        ]
        episode = EpisodeRecord(
            agent_id=agent.id,
            agent_name=agent.name,
            start_tick=max(0, tick_number - max(len(actions), 1) + 1),
            end_tick=tick_number,
            started_at=tick_datetime,
            ended_at=tick_datetime,
            goal=outcome.goal,
            planner=outcome.planner_type,
            initial_needs=initial_needs.model_copy(deep=True),
            final_needs=final_needs.model_copy(deep=True),
            actions=actions,
            summary=outcome.reason,
            success=outcome.action not in {None, "idle"},
        )

        result = self._reflection_engine.reflect(episode)
        self._emit_reflection_events(
            agent_id=agent.id,
            tick=tick_number,
            episode=episode,
            result=result,
        )
        for knowledge in result.output.knowledge:
            self._memory_service.upsert_semantic_knowledge(
                agent_id=agent.id,
                subject=knowledge.subject,
                predicate=knowledge.predicate,
                object_value=knowledge.object,
                confidence=knowledge.confidence,
                observed_at=tick_datetime,
                source_episode_id=str(episode.episode_id),
                lesson=result.output.lessons[0] if result.output.lessons else None,
            )

    def _emit_reflection_events(self, *, agent_id: UUID, tick: int, episode: EpisodeRecord, result) -> None:
        """Write concise reflection/knowledge events for timeline observability."""
        if self._event_service is None:
            return
        source_suffix = ""
        if result.error:
            source_suffix = f" (fallback: {result.source})"
        self._event_service.record(
            agent_id=agent_id,
            tick=tick,
            event_type=AgentEventType.REFLECTION,
            message=f"Episode reflected ({'success' if result.output.success else 'failure'}){source_suffix}: {result.output.summary}",
            metadata={
                "episode_id": str(episode.episode_id),
                "goal": episode.goal,
                "source": result.source,
                "error": result.error,
            },
        )
        for fact in result.output.knowledge:
            self._event_service.record(
                agent_id=agent_id,
                tick=tick,
                event_type=AgentEventType.KNOWLEDGE,
                message=f"{fact.subject} {fact.predicate} {fact.object}",
                metadata={
                    "episode_id": str(episode.episode_id),
                    "confidence": fact.confidence,
                    "goal": episode.goal,
                },
            )

    _NEED_LABELS = {
        NeedType.HUNGER: "Hunger",
        NeedType.THIRST: "Thirst",
        NeedType.FATIGUE: "Fatigue",
        NeedType.SAFETY: "Safety",
        NeedType.COMFORT: "Comfort",
        NeedType.SOCIAL: "Social",
    }

    def _emit_need_changes(self, agent: Agent, before: AgentNeeds, after: AgentNeeds, tick) -> None:
        """Record need_changed events for values that changed during need decay."""
        if self._event_service is None:
            return
        for need in NeedType:
            old_value = before.get(need)
            new_value = after.get(need)
            if old_value == new_value:
                continue
            label = self._NEED_LABELS[need]
            message = f"{label} {old_value} → {new_value}"
            if old_value <= 80 < new_value:
                message = f"{label} became critical: {new_value}"
            self._event_service.record(
                agent_id=agent.id,
                tick=tick.number,
                event_type=AgentEventType.NEED_CHANGED,
                message=message,
                metadata={"need": need.value, "before": old_value, "after": new_value},
            )

    def _emit_goal_changed(self, agent: Agent, goal: str, tick) -> None:
        """Record a goal_changed event only when the agent's goal actually changed."""
        if self._event_service is None:
            return
        if self._agent_last_goals.get(agent.id) == goal:
            return
        self._agent_last_goals[agent.id] = goal
        self._event_service.record(
            agent_id=agent.id,
            tick=tick.number,
            event_type=AgentEventType.GOAL_CHANGED,
            message=f"Goal set: {goal}",
            metadata={"goal": goal},
        )

    def _emit_state_changes(
        self,
        agent: Agent,
        before: AgentNeeds,
        after: AgentNeeds,
        action: str | None,
        tick,
    ) -> None:
        """Record state_changed events for need values altered by the executed action."""
        if self._event_service is None:
            return
        for need in (NeedType.HUNGER, NeedType.THIRST, NeedType.FATIGUE):
            old_value = before.get(need)
            new_value = after.get(need)
            if old_value == new_value:
                continue
            self._event_service.record(
                agent_id=agent.id,
                tick=tick.number,
                event_type=AgentEventType.STATE_CHANGED,
                message=f"{self._NEED_LABELS[need]} {old_value} → {new_value}",
                metadata={
                    "need": need.value,
                    "before": old_value,
                    "after": new_value,
                    "action": action,
                },
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
    reflection_engine: ReflectionEngine | None = None,
    event_service: AgentEventService | None = None,
) -> SimulationService:
    """Build the process-local simulation service using the default world clock settings."""
    return SimulationService(
        agents=agents,
        logs=logs,
        clock=SimulationClock(start_datetime=datetime.now(UTC)),
        memory_service=memory_service,
        brain=brain,
        reflection_engine=reflection_engine,
        event_service=event_service,
    )
