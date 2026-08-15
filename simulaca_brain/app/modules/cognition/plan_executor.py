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
from app.modules.world.models import Location, Resource
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
    thirst_change: int = 0
    hunger_change: int = 0
    fatigue_change: int = 0
    resource_changed: bool = False
    resource_details: dict | None = None
    agent_status: str = "IDLE"


class PlanExecutor:
    """Apply one plan step to agent needs and world location state."""

    def __init__(self,
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
            result = self._execute_drink(step, agent_id=agent_id, needs=needs, context=context, tick=tick, timestamp=timestamp)
        elif step.action == "eat":
            result = self._execute_eat(step, agent_id=agent_id, needs=needs, context=context, tick=tick, timestamp=timestamp)
        elif step.action == "sleep":
            result = self._execute_sleep(step, agent_id=agent_id, needs=needs, context=context, tick=tick, timestamp=timestamp)
        elif step.action == "wait":
            result = self._execute_wait(step, agent_id=agent_id, context=context, tick=tick, timestamp=timestamp)
        else:
            result = StepExecutionResult(
                action=step.action,
                target=step.target,
                success=False,
                message=f"Unknown action: {step.action}",
            )

        self._emit_action_event(step, result, agent_id=agent_id, tick=tick, context=context)
        return result

    def _execute_move(self, step: ActionPlanStep, *, agent_id: UUID, context: DecisionContext) -> StepExecutionResult:
        """Move agent to a connected location."""
        target = step.target
        if target is None:
            return StepExecutionResult(
                action="move",
                target=None,
                success=False,
                message="Move action requires a target location.",
            )

        allowed_locations = {loc.name.lower(): loc for loc in context.nearby_locations}
        if context.current_location is not None:
            allowed_locations[context.current_location.name.lower()] = context.current_location

        if target.lower() not in allowed_locations:
            return StepExecutionResult(
                action="move",
                target=target,
                success=False,
                message=f"Location '{target}' is not reachable from {context.current_location.name if context.current_location else 'current location'}.",
            )

        destination = allowed_locations[target.lower()]
        # Update agent location in repository
        try:
            self._world_repository.set_agent_location(agent_id, destination.id)
        except Exception:
            pass

        move_msg = f"Moved to {destination.name}" if not context.current_location else f"Moved {context.current_location.name} → {destination.name}"
        return StepExecutionResult(
            action="move",
            target=target,
            success=True,
            message=move_msg,
            location_changed=True,
            new_location=destination,
        )

    def _execute_drink(self, step: ActionPlanStep, *, agent_id: UUID, needs: AgentNeeds, context: DecisionContext, tick: int | None, timestamp: datetime | None) -> StepExecutionResult:
        """Drink water at the target location."""
        target = step.target
        location = PlanExecutor._resolve_target_location(context, target)

        if location is None:
            return StepExecutionResult(
                action="drink",
                target=target,
                success=False,
                message="No location to drink at.",
            )

        # Check for drinkable water - check resources at the location first
        has_drinkable = False
        resource_id = None
        resources_at_location = self._world_repository.list_resources(location.id)
        for res in resources_at_location:
            if res.affordances and "drink" in res.affordances and res.water_available:
                has_drinkable = True
                resource_id = res.id
                break
        # Also check entities
        if not has_drinkable:
            for entity in context.nearby_entities:
                if entity.location_id == location.id and (entity.attributes.get("drinkable") or entity.name.lower() == "water"):
                    has_drinkable = True
                    break

        if not has_drinkable:
            return StepExecutionResult(
                action="drink",
                target=target,
                success=False,
                message=f"No drinkable water at {target or context.current_location.name if context.current_location else 'current location'}.",
            )

        # Apply drink effect: thirst decreases by 70
        old_thirst = needs.thirst
        needs.thirst = max(0, needs.thirst - 70)
        thirst_change = needs.thirst - old_thirst  # negative value

        # If resource exists, deplete its water
        resource_changed = False
        resource_details = None
        if resource_id is not None:
            try:
                res = self._world_repository.get_resource(resource_id)
                if res.water_available:
                    old_water = res.water_available
                    res.water_available = False
                    self._world_repository.update_resource(res)
                    resource_changed = True
                    resource_details = {"water_available_before": old_water, "water_available_after": False}
            except Exception:
                pass

        new_thirst = needs.thirst
        msg = f"Drank water at {step.target}." if step.target else "Drank water."
        if thirst_change < 0:
            msg += f" Thirst {old_thirst} → {new_thirst}."

        return StepExecutionResult(
            action="drink",
            target=target,
            success=True,
            message=msg,
            thirst_change=thirst_change,
            resource_changed=resource_changed,
            resource_details=resource_details,
            agent_status="DRINKING",
        )

    def _execute_eat(self, step: ActionPlanStep, *, agent_id: UUID, needs: AgentNeeds, context: DecisionContext, tick: int | None, timestamp: datetime | None) -> StepExecutionResult:
        """Eat food at the target location."""
        target = step.target
        location = PlanExecutor._resolve_target_location(context, target)

        if location is None:
            return StepExecutionResult(
                action="eat",
                target=target,
                success=False,
                message="No location to eat at.",
            )

        # Check for edible food - check resources at the location
        has_food = False
        resource_id = None
        resources_at_location = self._world_repository.list_resources(location.id)
        for res in resources_at_location:
            if res.affordances and "eat" in res.affordances and res.food_quantity > 0:
                has_food = True
                resource_id = res.id
                break
        # Also check entities
        if not has_food:
            for entity in context.nearby_entities:
                if entity.location_id == location.id and (entity.attributes.get("edible") or entity.name.lower() in {"food", "apple", "bread"}):
                    has_food = True
                    break

        if not has_food:
            return StepExecutionResult(
                action="eat",
                target=target,
                success=False,
                message=f"No edible food at {target or context.current_location.name if context.current_location else 'current location'}.",
            )

        # Apply eat effect: hunger decreases by 60
        old_hunger = needs.hunger
        needs.hunger = max(0, needs.hunger - 60)
        hunger_change = needs.hunger - old_hunger  # negative value

        # Decrement resource food_quantity
        resource_changed = False
        resource_details = None
        if resource_id is not None:
            try:
                res = self._world_repository.get_resource(resource_id)
                new_q = max(0, res.food_quantity - 1)
                res.food_quantity = new_q
                self._world_repository.update_resource(res)
                resource_changed = True
                resource_details = {"food_quantity_before": res.food_quantity + 1, "food_quantity_after": new_q}
            except Exception:
                pass

        new_hunger = needs.hunger
        msg = f"Ate food at {step.target}." if step.target else "Ate food."
        if hunger_change < 0:
            msg += f" Hunger {old_hunger} → {new_hunger}."

        return StepExecutionResult(
            action="eat",
            target=target,
            success=True,
            message=msg,
            hunger_change=hunger_change,
            resource_changed=resource_changed,
            resource_details=resource_details,
            agent_status="EATING",
        )

    def _execute_sleep(self, step: ActionPlanStep, *, agent_id: UUID, needs: AgentNeeds, context: DecisionContext, tick: int | None, timestamp: datetime | None) -> StepExecutionResult:
        """Sleep to recover fatigue."""
        target = step.target
        location = context.current_location

        if location is None:
            return StepExecutionResult(
                action="sleep",
                target=target,
                success=False,
                message="No sleeping location available.",
            )

        # Check that we have a bed or suitable sleeping location
        has_bed = False
        resources_at_location = self._world_repository.list_resources(location.id)
        for res in resources_at_location:
            if res.affordances and "sleep" in res.affordances:
                has_bed = True
                break
        # Also check entities for bed
        if not has_bed:
            for entity in context.nearby_entities:
                if entity.location_id == location.id and entity.name.lower() == "bed":
                    has_bed = True
                    break

        if not has_bed:
            return StepExecutionResult(
                action="sleep",
                target=target,
                success=False,
                message="No bed available for sleeping.",
            )

        # Apply sleep effect: fatigue decreases by 50
        old_fatigue = needs.fatigue
        needs.fatigue = max(0, needs.fatigue - 50)
        fatigue_change = needs.fatigue - old_fatigue  # negative value

        new_fatigue = needs.fatigue
        message = f"Slept at {location.name}."
        if fatigue_change < 0:
            message += f" Fatigue {old_fatigue} → {new_fatigue}."

        return StepExecutionResult(
            action="sleep",
            target=target,
            success=True,
            message=message,
            fatigue_change=fatigue_change,
            agent_status="SLEEPING",
        )

    def _execute_wait(self, step: ActionPlanStep, *, agent_id: UUID, context: DecisionContext, tick: int | None, timestamp: datetime | None) -> StepExecutionResult:
        """Wait without changing state."""
        return StepExecutionResult(
            action="wait",
            target=step.target,
            success=True,
            message="Waited.",
            agent_status="WAITING",
        )

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
            "agent_status": result.agent_status,
        }
        if result.new_location is not None:
            metadata["new_location"] = result.new_location.name
        if result.resource_changed and result.resource_details is not None:
            metadata["resource_changed"] = result.resource_details
        if result.thirst_change != 0:
            metadata["thirst_change"] = result.thirst_change
        if result.hunger_change != 0:
            metadata["hunger_change"] = result.hunger_change
        if result.fatigue_change != 0:
            metadata["fatigue_change"] = result.fatigue_change
        self._event_service.record(
            agent_id=agent_id,
            tick=tick,
            event_type=AgentEventType.ACTION_COMPLETED,
            message=result.message,
            metadata=metadata,
        )

    @staticmethod
    def is_complete(plan: ActionPlan, step_index: int) -> bool:
        """Return True when all plan steps have been executed."""
        return step_index >= len(plan.steps)
