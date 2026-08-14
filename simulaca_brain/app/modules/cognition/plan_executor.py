"""Execute one validated plan step per simulation tick."""

import logging
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.activity.models import AgentEventType
from app.modules.activity.service import AgentEventService
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.action_plan import ActionPlan, ActionPlanStep
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.exceptions import InvalidPlanError
from app.modules.world.models import Location
from app.modules.world.repository import WorldRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StepExecutionResult:
    """Outcome of executing one plan step."""

    action: str
    target: str | None
    success: bool
    message: str
    location_changed: bool = False
    new_location: Location | None = None


class PlanExecutor:
    """Apply one plan step to agent needs and world location state."""

    def __init__(
        self,
        world_repository: WorldRepository,
        event_service: AgentEventService | None = None,
    ) -> None:
        self._world_repository = world_repository
        self._event_service = event_service

    def execute_step(
        self,
        step: ActionPlanStep,
        *,
        agent_id: UUID,
        needs: AgentNeeds,
        context: DecisionContext,
        tick: int | None = None,
        timestamp: datetime | None = None,
    ) -> StepExecutionResult:
        """Execute a single plan step without mutating external persistence."""
        logger.debug(
            "EXECUTOR_START action=%s target=%s current_location=%s nearby_locations=%s",
            step.action,
            step.target,
            context.current_location.name if context.current_location else None,
            [loc.name for loc in context.nearby_locations],
        )
        result: StepExecutionResult
        if step.action == "move":
            result = self._execute_move(step, agent_id=agent_id, context=context)
        elif step.action == "drink":
            if not self._can_drink_at(context, step.target):
                raise InvalidPlanError(
                    f"No drinkable water at '{step.target or context.current_location.name if context.current_location else 'current location'}'."
                )
            self._apply_drink(needs)
            result = StepExecutionResult(
                action="drink",
                target=step.target,
                success=True,
                message=f"Drank water at {step.target}." if step.target else "Drank water.",
            )
        elif step.action == "eat":
            if not self._can_eat_at(context, step.target):
                raise InvalidPlanError(
                    f"No edible food at '{step.target or context.current_location.name if context.current_location else 'current location'}'."
                )
            self._apply_eat(needs)
            result = StepExecutionResult(
                action="eat",
                target=step.target,
                success=True,
                message=f"Ate food at {step.target}." if step.target else "Ate food.",
            )
        elif step.action == "sleep":
            self._apply_sleep(needs)
            result = StepExecutionResult(action="sleep", target=step.target, success=True, message="Rested.")
        elif step.action == "idle":
            result = StepExecutionResult(action="idle", target=step.target, success=True, message="Idled.")
        else:
            raise InvalidPlanError(f"Unsupported action '{step.action}'.")

        self._emit_action_event(step, result, agent_id=agent_id, tick=tick, context=context)
        return result

    @staticmethod
    def current_step(plan: ActionPlan, step_index: int) -> ActionPlanStep | None:
        """Return the step at ``step_index`` when the plan is still active."""
        if step_index < 0 or step_index >= len(plan.steps):
            return None
        return plan.steps[step_index]

    @staticmethod
    def is_complete(plan: ActionPlan, step_index: int) -> bool:
        """Return whether every step in ``plan`` has been executed."""
        return step_index >= len(plan.steps)

    def _execute_move(self, step: ActionPlanStep, *, agent_id: UUID, context: DecisionContext) -> StepExecutionResult:
        target_name = (step.target or "").lower()
        location_lookup = {loc.name.lower(): loc for loc in context.nearby_locations}
        if context.current_location is not None:
            location_lookup[context.current_location.name.lower()] = context.current_location

        destination = location_lookup.get(target_name)
        if destination is None:
            raise InvalidPlanError(f"Cannot move to unknown location '{step.target}'.")

        if context.current_location is not None and destination.id == context.current_location.id:
            return StepExecutionResult(
                action="move",
                target=step.target,
                success=True,
                message=f"Already at {destination.name}.",
            )

        self._world_repository.set_agent_location(agent_id, destination.id)
        origin = context.current_location.name if context.current_location is not None else "?"
        return StepExecutionResult(
            action="move",
            target=destination.name,
            success=True,
            message=f"Moved {origin} → {destination.name}.",
            location_changed=True,
            new_location=destination,
        )

    def _emit_action_event(
        self,
        step: ActionPlanStep,
        result: StepExecutionResult,
        *,
        agent_id: UUID,
        tick: int | None,
        context: DecisionContext,
    ) -> None:
        """Record an observable action_completed event for the timeline."""
        if self._event_service is None or tick is None:
            return
        metadata: dict = {
            "action": result.action,
            "target": result.target,
            "success": result.success,
        }
        if result.new_location is not None:
            metadata["new_location"] = result.new_location.name
        if context.current_location is not None:
            metadata["before_location"] = context.current_location.name
        self._event_service.record(
            agent_id=agent_id,
            tick=tick,
            event_type=AgentEventType.ACTION_COMPLETED,
            message=result.message,
            metadata=metadata,
        )

    @staticmethod
    def _can_drink_at(context: DecisionContext, target: str | None) -> bool:
        """Return whether ``target`` (or the current location) has drinkable water."""
        location = PlanExecutor._resolve_target_location(context, target)
        if location is None:
            return False
        for entity in context.nearby_entities:
            attributes = entity.attributes or {}
            if entity.location_id == location.id and (
                attributes.get("drinkable") or entity.name.lower() == "water"
            ):
                return True
        name = location.name.lower()
        return any(keyword in name for keyword in ("river", "water", "well", "spring", "lake", "pond", "stream"))

    @staticmethod
    def _can_eat_at(context: DecisionContext, target: str | None) -> bool:
        """Return whether ``target`` (or the current location) has edible food."""
        location = PlanExecutor._resolve_target_location(context, target)
        if location is None:
            return False
        for entity in context.nearby_entities:
            attributes = entity.attributes or {}
            if entity.location_id == location.id and (
                attributes.get("edible") or entity.name.lower() in {"food", "apple", "bread"}
            ):
                return True
        name = location.name.lower()
        return any(keyword in name for keyword in ("shop", "kitchen", "market", "farm", "garden", "orchard"))

    @staticmethod
    def _resolve_target_location(context: DecisionContext, target: str | None) -> Location | None:
        """Resolve a plan target name to a ``Location`` in the current context."""
        if target is None:
            return context.current_location
        target_key = target.strip().lower()
        for location in context.nearby_locations:
            if location.name.lower() == target_key:
                return location
        if context.current_location is not None and context.current_location.name.lower() == target_key:
            return context.current_location
        return None

    @staticmethod
    def _apply_drink(needs: AgentNeeds) -> None:
        needs.thirst = max(0, needs.thirst - 70)

    @staticmethod
    def _apply_eat(needs: AgentNeeds) -> None:
        needs.hunger = max(0, needs.hunger - 60)

    @staticmethod
    def _apply_sleep(needs: AgentNeeds) -> None:
        needs.fatigue = max(0, needs.fatigue - 80)
