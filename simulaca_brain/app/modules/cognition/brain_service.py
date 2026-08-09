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

from app.modules.agent.models import Agent
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.brain_state import (
    AgentDecisionMetadata,
    BrainStateStore,
    LLMRequestLogEntry,
)
from app.modules.cognition.context_builder import ContextBuilder
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
    ) -> None:
        self._context_builder = context_builder
        self._planner = planner
        self._executor = executor
        self._store = store

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

        step = PlanExecutor.current_step(plan, step_index)
        executed_action = None
        target: str | None = None
        if step is not None:
            result = self._executor.execute_step(
                step,
                agent_id=agent.id,
                needs=needs,
                context=context,
            )
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

