"""Execute one validated plan step per simulation tick."""

from dataclasses import dataclass
from uuid import UUID

from app.modules.agent.state import AgentNeeds
from app.modules.cognition.action_plan import ActionPlan, ActionPlanStep
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.exceptions import InvalidPlanError
from app.modules.world.models import Location
from app.modules.world.repository import WorldRepository


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

    def __init__(self, world_repository: WorldRepository) -> None:
        self._world_repository = world_repository

    def execute_step(
        self,
        step: ActionPlanStep,
        *,
        agent_id: UUID,
        needs: AgentNeeds,
        context: DecisionContext,
    ) -> StepExecutionResult:
        """Execute a single plan step without mutating external persistence."""
        if step.action == "move":
            return self._execute_move(step, agent_id=agent_id, context=context)
        if step.action == "drink":
            self._apply_drink(needs)
            return StepExecutionResult(action="drink", target=step.target, success=True, message="Drank water.")
        if step.action == "eat":
            self._apply_eat(needs)
            return StepExecutionResult(action="eat", target=step.target, success=True, message="Ate food.")
        if step.action == "sleep":
            self._apply_sleep(needs)
            return StepExecutionResult(action="sleep", target=step.target, success=True, message="Rested.")
        if step.action == "idle":
            return StepExecutionResult(action="idle", target=step.target, success=True, message="Idled.")

        raise InvalidPlanError(f"Unsupported action '{step.action}'.")

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
        return StepExecutionResult(
            action="move",
            target=destination.name,
            success=True,
            message=f"Moved to {destination.name}.",
            location_changed=True,
            new_location=destination,
        )

    @staticmethod
    def _apply_drink(needs: AgentNeeds) -> None:
        needs.thirst = max(0, needs.thirst - 70)

    @staticmethod
    def _apply_eat(needs: AgentNeeds) -> None:
        needs.hunger = max(0, needs.hunger - 60)

    @staticmethod
    def _apply_sleep(needs: AgentNeeds) -> None:
        needs.fatigue = max(0, needs.fatigue - 80)
