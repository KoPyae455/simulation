"""Planner selection with optional rule-based fallback."""

import logging
from dataclasses import dataclass

from app.modules.cognition.action_plan import ActionPlan
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.exceptions import InvalidPlanError, LLMPlanningError
from app.modules.cognition.llm_planner import LLMPlanner
from app.modules.cognition.plan_validator import PlanValidator
from app.modules.cognition.planner import RuleBasedPlanner

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PlanningOutcome:
    """Planner output plus metadata for logging and dashboards."""

    plan: ActionPlan
    planner_type: str
    status: str
    latency_ms: int | None = None
    model: str | None = None
    error_type: str | None = None
    fallback_reason: str | None = None
    reasoning_summary: str = ""


class CompositePlanner:
    """Route planning to the configured backend with optional fallback."""

    def __init__(
        self,
        *,
        planner_type: str,
        rule_based_planner: RuleBasedPlanner,
        llm_planner: LLMPlanner | None = None,
        fallback_to_rules: bool = True,
        validator: PlanValidator | None = None,
    ) -> None:
        self._planner_type = planner_type.lower()
        self._rule_based_planner = rule_based_planner
        self._llm_planner = llm_planner
        self._fallback_to_rules = fallback_to_rules
        self._validator = validator or PlanValidator()

    @property
    def configured_planner_type(self) -> str:
        return self._planner_type

    def plan(self, context: DecisionContext) -> PlanningOutcome:
        """Produce a validated plan using the configured planner."""
        if self._planner_type == "llm":
            return self._plan_with_llm(context)
        return self._plan_with_rules(context)

    def _plan_with_rules(self, context: DecisionContext) -> PlanningOutcome:
        plan = self._validator.validate(self._rule_based_planner.plan(context), context)
        return PlanningOutcome(
            plan=plan,
            planner_type=self._rule_based_planner.planner_type,
            status="success",
            reasoning_summary=plan.reasoning_summary,
        )

    def _plan_with_llm(self, context: DecisionContext) -> PlanningOutcome:
        if self._llm_planner is None:
            if self._fallback_to_rules:
                return self._fallback(context, reason="LLM planner is not configured.")
            raise LLMPlanningError("LLM planner is not configured.")

        try:
            result = self._llm_planner.plan(context)
            logger.debug(
                "LLM_PLANNER_SUCCESS agent=%s tick=%s goal=%s steps=%s",
                context.agent_name,
                context.tick,
                result.plan.goal,
                [{"action": s.action, "target": s.target} for s in result.plan.steps],
            )
            return PlanningOutcome(
                plan=result.plan,
                planner_type=self._llm_planner.planner_type,
                status=result.status,
                latency_ms=result.latency_ms,
                model=result.model,
                reasoning_summary=result.plan.reasoning_summary,
            )
        except (LLMPlanningError, InvalidPlanError, TimeoutError) as exc:
            if not self._fallback_to_rules:
                raise
            reason = getattr(exc, "message", str(exc))
            error_type = type(exc).__name__
            logger.debug(
                "LLM_PLANNER_FALLBACK agent=%s tick=%s goal=%s error=%s error_type=%s",
                context.agent_name,
                context.tick,
                context.current_goal,
                reason,
                error_type,
            )
            fallback = self._fallback(context, reason=reason)
            return PlanningOutcome(
                plan=fallback.plan,
                planner_type="llm",
                status="fallback",
                error_type=error_type,
                fallback_reason=reason,
                reasoning_summary=fallback.reasoning_summary,
            )

    def _fallback(self, context: DecisionContext, *, reason: str) -> PlanningOutcome:
        plan = self._validator.validate(self._rule_based_planner.plan(context), context)
        return PlanningOutcome(
            plan=plan,
            planner_type="llm",
            status="fallback",
            fallback_reason=reason,
            reasoning_summary=plan.reasoning_summary,
        )
