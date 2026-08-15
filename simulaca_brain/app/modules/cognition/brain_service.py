"""Brain orchestration: context → planner → validator → executor → brain store.

Wires the existing V0.6/V0.7 cognition ports together and advances each
agent exactly one validated plan step per simulation tick. The LLM never
mutates agent state directly: the pipeline produces a structured
ActionPlan, which is validated, then executed one step at a time by the
``PlanExecutor``, with the current plan cursor persisted in the
``BrainStateStore`` so a multi-step plan is consumed across ticks.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.activity.models import AgentEventType
from app.modules.activity.service import AgentEventService
from app.modules.agent.models import Agent
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.brain_state import (
    AgentDecisionMetadata,
    BrainStateStore,
    LLMRequestLogEntry,
)
from app.modules.cognition.context_builder import ContextBuilder
from app.modules.cognition.exceptions import InvalidPlanError
from app.modules.cognition.plan_executor import PlanExecutor
from app.modules.cognition.planner_service import CompositePlanner, PlanningOutcome

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AgentStepOutcome:
    """Result of one agent's cognitive step for a single simulation tick."""

    needs: AgentNeeds
    goal: str
    planner_type: str
    action: str | None
    target: str | None
    reason: str
    completed: bool
    decision: AgentDecisionMetadata


class BrainService:
    """Coordinate planning, one-step execution, and brain metadata per agent."""

    def __init__(
        self,
        *,
        context_builder: ContextBuilder,
        planner: CompositePlanner,
        executor: PlanExecutor,
        store: BrainStateStore,
        event_service: AgentEventService | None = None,
    ) -> None:
        self._context_builder = context_builder
        self._planner = planner
        self._executor = executor
        self._store = store
        self._event_service = event_service

    @property
    def store(self) -> BrainStateStore:
        """Expose the brain metadata store for read-only API access."""
        return self._store

    @property
    def configured_planner_type(self) -> str:
        """Return the planner backend the service is configured to use."""
        return self._planner.configured_planner_type

    def process_agent(
        self,
        agent: Agent,
        needs: AgentNeeds,
        *,
        tick: int,
        simulation_datetime: datetime,
    ) -> AgentStepOutcome:
        """Advance ``agent`` by exactly one validated plan step for the tick.

        A fresh plan is generated (via the configured planner, which may
        invoke the LLM) only when no active, incomplete plan exists for the
        agent. Otherwise the stored plan is reused so multi-step plans are
        consumed one step per tick.
        """
        context = self._context_builder.build(
            agent,
            tick=tick,
            simulation_datetime=simulation_datetime,
            needs=needs,
        )

        decision = self._store.get_decision(agent.id)
        step_index = self._store.current_step_index(agent.id)
        reuse_existing = (
            decision is not None
            and decision.plan is not None
            and not PlanExecutor.is_complete(decision.plan, step_index)
        )

        if reuse_existing:
            plan = decision.plan
            planner_type = decision.planner_type
            goal = decision.goal
            latency_ms = None
            model = decision.model
            fallback_reason = decision.fallback_reason
            reasoning = decision.reasoning_summary or ""
            planned_this_tick = False
        else:
            outcome = self._plan(context)
            plan = outcome.plan
            planner_type = outcome.planner_type
            goal = plan.goal
            latency_ms = outcome.latency_ms
            model = outcome.model
            fallback_reason = outcome.fallback_reason
            reasoning = outcome.reasoning_summary
            step_index = 0
            self._store.reset_step_index(agent.id)
            planned_this_tick = True
            self._record_llm_request(agent.id, tick, outcome)
            self._emit_planning_events(agent, tick, outcome)

        step = plan.steps[step_index] if step_index < len(plan.steps) else None
        executed_action = None
        target: str | None = None
        result = None
        logger.debug(
            "BRAIN_EXECUTE agent=%s tick=%s goal=%s planner=%s step_index=%s step_action=%s step_target=%s steps=%s",
            agent.name,
            tick,
            goal,
            planner_type,
            step_index,
            step.action if step else None,
            step.target if step else None,
            [{"action": s.action, "target": s.target} for s in plan.steps],
        )
        if step is not None:
            try:
                result = self._executor.execute_step(
                    step,
                    agent_id=agent.id,
                    needs=needs,
                    context=context,
                    tick=tick,
                    timestamp=simulation_datetime,
                )
            except InvalidPlanError as exc:
                logger.debug(
                    "BRAIN_EXECUTE_FAIL agent=%s tick=%s action=%s target=%s error=%s",
                    agent.name,
                    tick,
                    step.action if step else None,
                    step.target if step else None,
                    exc.message,
                )
                self._emit_error(agent, tick, exc.message)
                self._store.reset_step_index(agent.id)
                executed_action = "idle"
                target = None
                reasoning = f"Plan execution failed: {exc.message}"
            else:
                executed_action = result.action
                target = step.target
                self._store.set_step_index(agent.id, step_index + 1)
                if result.location_changed and result.new_location is not None:
                    logger.info(
                        "Agent %s moved to %s at tick %s",
                        agent.name,
                        result.new_location.name,
                        tick,
                    )
        elif step is None and reuse_existing:
            self._store.set_step_index(agent.id, step_index + 1)

        completed = PlanExecutor.is_complete(plan, self._store.current_step_index(agent.id))
        status = "completed" if completed else "active"
        metadata = AgentDecisionMetadata(
            agent_id=agent.id,
            agent_name=agent.name,
            tick=tick,
            timestamp=simulation_datetime,
            planner_type=planner_type,
            goal=goal,
            status=status,
            plan=plan,
            executed_action=executed_action,
            latency_ms=latency_ms,
            fallback_reason=fallback_reason,
            reasoning_summary=reasoning,
            model=model,
        )
        self._store.record_decision(metadata)
        if planned_this_tick and planner_type == "llm" and latency_ms is not None:
            self._record_llm_request(agent.id, tick, None, metadata=metadata)

        return AgentStepOutcome(
            needs=needs,
            goal=goal,
            planner_type=planner_type,
            action=executed_action,
            target=target,
            reason=reasoning or f"Goal={goal}",
            completed=completed,
            decision=metadata,
        )

    def _plan(self, context) -> PlanningOutcome:
        """Route planning to the configured planner (LLM or rules + fallback)."""
        return self._planner.plan(context)

    def _emit_planning_events(self, agent: Agent, tick: int, outcome: PlanningOutcome) -> None:
        """Record concise decision / plan-created / fallback events (no chain-of-thought)."""
        if self._event_service is None:
            return
        agent_id = agent.id
        if outcome.status == "fallback":
            self._event_service.record(
                agent_id=agent_id,
                tick=tick,
                event_type=AgentEventType.FALLBACK,
                message="LLM planner failed → RuleBasedPlanner used",
                metadata={
                    "reason": outcome.fallback_reason,
                    "error_type": outcome.error_type,
                },
            )
            return

        self._event_service.record(
            agent_id=agent_id,
            tick=tick,
            event_type=AgentEventType.DECISION,
            message=f"Goal → {outcome.plan.goal.capitalize()}",
            metadata={
                "goal": outcome.plan.goal,
                "planner": outcome.planner_type,
                "model": outcome.model,
            },
        )
        self._event_service.record(
            agent_id=agent_id,
            tick=tick,
            event_type=AgentEventType.PLAN_CREATED,
            message=self._summarize_steps(outcome.plan),
            metadata={
                "goal": outcome.plan.goal,
                "plan_id": str(outcome.plan.plan_id),
                "planner": outcome.planner_type,
                "model": outcome.model,
                "steps": [
                    {"action": step.action, "target": step.target}
                    for step in outcome.plan.steps
                ],
            },
        )

    @staticmethod
    def _summarize_steps(plan) -> str:
        """Render plan steps as a short human-readable summary."""
        parts: list[str] = []
        for step in plan.steps:
            parts.append(f"{step.action} → {step.target}" if step.target else step.action)
        return "; ".join(parts)

    def _emit_error(self, agent: Agent, tick: int, message: str) -> None:
        """Record an observable error event without leaking internals."""
        if self._event_service is None:
            return
        self._event_service.record(
            agent_id=agent.id,
            tick=tick,
            event_type=AgentEventType.ERROR,
            message=f"Step failed: {message}",
            metadata={"action": message},
        )

    def _record_llm_request(
        self,
        agent_id: UUID,
        tick: int,
        outcome: PlanningOutcome | None,
        *,
        metadata: AgentDecisionMetadata | None = None,
    ) -> None:
        """Capture safe LLM-request metadata when an LLM attempt occurred."""
        if outcome is not None and outcome.planner_type != "llm":
            return
        entry = LLMRequestLogEntry(
            agent_id=agent_id,
            tick=tick,
            model=(
                outcome.model
                if outcome is not None
                else (metadata.model if metadata else None)
            ),
            planner_type="llm",
            latency_ms=(
                outcome.latency_ms
                if outcome is not None
                else (metadata.latency_ms if metadata else None)
            ),
            status=(
                outcome.status
                if outcome is not None
                else (metadata.status if metadata else "active")
            ),
            error_type=outcome.error_type if outcome is not None else None,
            plan_id=(
                outcome.plan.plan_id
                if outcome is not None and outcome.plan
                else None
            ),
        )
        self._store.record_llm_request(entry)

