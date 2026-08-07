"""Planner port and rule-based implementation."""

from typing import Protocol

from app.modules.cognition.action_plan import ActionPlan, ActionPlanStep
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.goal_generator import GoalGenerator


class ActionPlanner(Protocol):
    """Port for producing an action plan from a decision context."""

    @property
    def planner_type(self) -> str:
        """Return a stable identifier for this planner implementation."""

    def plan(self, context: DecisionContext) -> ActionPlan:
        """Produce an action plan for the supplied context."""


class RuleBasedPlanner:
    """Deterministic planner that maps goals to minimal valid action sequences."""

    planner_type = "rule_based"

    def __init__(self, goal_generator: GoalGenerator | None = None) -> None:
        self._goal_generator = goal_generator or GoalGenerator()

    def plan(self, context: DecisionContext) -> ActionPlan:
        """Build a minimal plan for ``context.current_goal``."""
        goal = context.current_goal
        steps: list[ActionPlanStep] = []

        if goal == "drink":
            target = self._find_drink_location(context)
            steps.extend(self._movement_if_needed(context, target))
            steps.append(ActionPlanStep(action="drink", target=target, parameters={}))
        elif goal == "eat":
            target = self._find_eat_location(context)
            steps.extend(self._movement_if_needed(context, target))
            steps.append(ActionPlanStep(action="eat", target=target, parameters={}))
        elif goal == "sleep":
            target = context.current_location.name if context.current_location else None
            steps.append(ActionPlanStep(action="sleep", target=target, parameters={}))
        else:
            steps.append(ActionPlanStep(action="idle", target=None, parameters={}))

        return ActionPlan(
            goal=goal,
            reasoning_summary=self._goal_generator.reason_for(goal, context.needs),
            steps=steps,
        )

    @staticmethod
    def _movement_if_needed(context: DecisionContext, target: str | None) -> list[ActionPlanStep]:
        if target is None:
            return []
        current_name = context.current_location.name.lower() if context.current_location else ""
        if current_name == target.lower():
            return []
        return [ActionPlanStep(action="move", target=target, parameters={})]

    @staticmethod
    def _find_drink_location(context: DecisionContext) -> str | None:
        for entity in context.nearby_entities:
            attributes = entity.attributes or {}
            if attributes.get("drinkable") or entity.name.lower() == "water":
                for location in context.nearby_locations:
                    if location.id == entity.location_id:
                        return location.name
        for location in context.nearby_locations:
            if "river" in location.name.lower():
                return location.name
        return context.current_location.name if context.current_location else None

    @staticmethod
    def _find_eat_location(context: DecisionContext) -> str | None:
        for entity in context.nearby_entities:
            attributes = entity.attributes or {}
            if attributes.get("edible") or entity.name.lower() in {"food", "apple", "bread"}:
                for location in context.nearby_locations:
                    if location.id == entity.location_id:
                        return location.name
        for location in context.nearby_locations:
            if "shop" in location.name.lower() or "kitchen" in location.name.lower():
                return location.name
        return context.current_location.name if context.current_location else None
