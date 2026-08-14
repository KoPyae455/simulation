"""Validate action plans against the action registry and decision context."""

from app.modules.cognition.action_plan import ActionPlan, ActionPlanStep
from app.modules.cognition.action_registry import ActionRegistry
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.exceptions import InvalidPlanError


class PlanValidator:
    """Ensure proposed plans only use registered actions and valid targets."""

    def validate(self, plan: ActionPlan, context: DecisionContext) -> ActionPlan:
        """Validate ``plan`` and return it when every step is executable."""
        if not plan.steps:
            raise InvalidPlanError("Action plans must contain at least one step.")

        allowed_locations = {loc.name.lower(): loc for loc in context.nearby_locations}
        if context.current_location is not None:
            allowed_locations[context.current_location.name.lower()] = context.current_location

        for index, step in enumerate(plan.steps):
            self._validate_step(step, allowed_locations, context=context, step_index=index)

        return plan

    def _validate_step(
        self,
        step: ActionPlanStep,
        allowed_locations: dict,
        context: DecisionContext,
        *,
        step_index: int,
    ) -> None:
        if not ActionRegistry.is_valid(step.action):
            raise InvalidPlanError(
                f"Unknown action '{step.action}' at step {step_index}.",
                details={"action": step.action, "step_index": step_index},
            )

        definition = ActionRegistry.get(step.action)
        assert definition is not None

        if definition.requires_target and not step.target:
            raise InvalidPlanError(
                f"Action '{step.action}' requires a target at step {step_index}.",
                details={"action": step.action, "step_index": step_index},
            )

        if step.action == "move" and step.target is not None:
            if step.target.lower() not in allowed_locations:
                raise InvalidPlanError(
                    f"Unknown move target '{step.target}' at step {step_index}.",
                    details={"target": step.target, "step_index": step_index},
                )

        if step.action in {"drink", "eat"} and step.target is not None:
            target_key = step.target.lower()
            entity_names = {entity.name.lower() for entity in context.nearby_entities}
            if target_key not in allowed_locations and target_key not in entity_names:
                raise InvalidPlanError(
                    f"Unknown target '{step.target}' for action '{step.action}' at step {step_index}.",
                    details={"target": step.target, "action": step.action, "step_index": step_index},
                )
