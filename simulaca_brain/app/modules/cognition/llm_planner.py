"""LLM-backed cognitive planner."""

import logging
import time
from dataclasses import dataclass

from app.core.llm.base import LLMProvider
from app.modules.cognition.action_plan import ActionPlan
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.exceptions import LLMPlanningError
from app.modules.cognition.llm_response_parser import parse_action_plan
from app.modules.cognition.plan_validator import PlanValidator
from app.modules.cognition.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class LLMPlanningResult:
    """Outcome metadata for one LLM planning attempt."""

    plan: ActionPlan
    latency_ms: int
    model: str
    status: str = "success"
    error_type: str | None = None


class LLMPlanner:
    """Generate validated action plans through an injected LLM provider."""

    planner_type = "llm"

    def __init__(
        self,
        provider: LLMProvider,
        prompt_builder: PromptBuilder | None = None,
        validator: PlanValidator | None = None,
    ) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()
        self._validator = validator or PlanValidator()

    @property
    def model(self) -> str:
        return self._provider.model

    def plan(self, context: DecisionContext) -> LLMPlanningResult:
        """Request, parse, and validate an action plan from the LLM."""
        user_prompt = self._prompt_builder.build_user_prompt(context)
        system_prompt = self._prompt_builder.build_system_prompt()
        started = time.perf_counter()

        try:
            raw_response = self._provider.generate(user_prompt, system_prompt=system_prompt)
            logger.debug(
                "LLM_RESPONSE_RECEIVED agent=%s tick=%s goal=%s length=%s",
                context.agent_name,
                context.tick,
                context.current_goal,
                len(raw_response) if raw_response else 0,
            )
            action_plan = parse_action_plan(raw_response)
            logger.debug(
                "LLM_PARSED_PLAN agent=%s tick=%s goal=%s steps=%s",
                context.agent_name,
                context.tick,
                action_plan.goal,
                [{"action": s.action, "target": s.target} for s in action_plan.steps],
            )
            validated_plan = self._validator.validate(action_plan, context)
            logger.debug(
                "LLM_VALIDATED_PLAN agent=%s tick=%s goal=%s steps=%s",
                context.agent_name,
                context.tick,
                validated_plan.goal,
                [{"action": s.action, "target": s.target} for s in validated_plan.steps],
            )
        except LLMPlanningError:
            raise
        except Exception as exc:
            error_type = type(exc).__name__
            raise LLMPlanningError(str(exc), details={"error_type": error_type}) from exc

        latency_ms = int((time.perf_counter() - started) * 1000)
        return LLMPlanningResult(
            plan=validated_plan,
            latency_ms=latency_ms,
            model=self._provider.model,
            status="success",
        )
