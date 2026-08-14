"""Parse, normalize, and validate structured LLM planning responses.

The LLM is a free-form text model, so its action names may arrive as any
of many human-readable variations (e.g. "go to river", "move to River",
"drink water"). A canonical action vocabulary -- move, drink, eat, sleep,
idle -- is the only set the executor can run. This module normalizes every
LLM response onto that vocabulary before returning an ``ActionPlan``.
"""

import json
import re

from pydantic import ValidationError

from app.modules.cognition.action_plan import ActionPlan, ActionPlanStep
from app.modules.cognition.exceptions import LLMPlanningError

# Canonical action -> accepted aliases (compared case-insensitively).
_ACTION_ALIASES: dict[str, set[str]] = {
    "move": {
        "move", "go", "goto", "walk", "travel", "migrate",
        "move to", "go to", "go over", "walk to", "travel to", "head to",
        "move toward", "travel toward", "go towards", "move_towards",
    },
    "drink": {
        "drink", "drink water", "hydrate", "get water", "take water",
        "drink from", "drink at", "drink at the", "sip", "consume water",
    },
    "eat": {
        "eat", "eat food", "consume", "eat at", "take food", "feed", "have food",
    },
    "sleep": {
        "sleep", "rest", "nap", "rest at", "sleep at", "recover", "lie down",
    },
    "idle": {
        "idle", "wait", "stay", "do nothing", "stand", "rest here", "idle here",
    },
}

# Canonical goal -> accepted aliases.
_GOAL_ALIASES: dict[str, set[str]] = {
    "drink": {"drink", "drink water", "hydrate", "thirst", "get drink", "quench"},
    "eat": {"eat", "eat food", "hunger", "food", "feed", "satiate"},
    "sleep": {"sleep", "rest", "nap", "fatigue", "tired", "restore energy"},
    "idle": {"idle", "wait", "none", "do nothing", "relax"},
}


def parse_action_plan(raw_response: str) -> ActionPlan:
    """Parse ``raw_response`` into a normalized ``ActionPlan`` or raise ``LLMPlanningError``."""
    payload_text = _extract_json(raw_response)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise LLMPlanningError("LLM response was not valid JSON.") from exc

    try:
        plan = ActionPlan.model_validate(payload)
    except ValidationError as exc:
        raise LLMPlanningError("LLM response did not match the ActionPlan schema.") from exc

    return normalize_action_plan(plan)


def normalize_action_plan(plan: ActionPlan) -> ActionPlan:
    """Map free-form LLM action/goal names onto the canonical vocabulary.

    Every step's ``action`` is normalized to one of ``move / drink / eat /
    sleep / idle``. Any alias that cannot be matched is left untouched so the
    downstream ``PlanValidator`` can reject it and trigger the rule-based
    fallback rather than silently inventing an action.
    """
    goal = normalize_goal(plan.goal) or plan.goal
    steps = [
        ActionPlanStep(
            action=normalize_action(step.action) or step.action,
            target=step.target,
            parameters=step.parameters,
        )
        for step in plan.steps
    ]
    return ActionPlan(
        plan_id=plan.plan_id,
        goal=goal,
        reasoning_summary=plan.reasoning_summary,
        steps=steps,
    )


def normalize_action(value: str | None) -> str | None:
    """Return the canonical action for a free-form action string, or ``None``."""
    if not value:
        return None
    key = value.strip().lower()
    for canonical, aliases in _ACTION_ALIASES.items():
        if key == canonical or key in aliases:
            return canonical
    # Loose containment match, e.g. "I move to the river" -> "move".
    for canonical, aliases in _ACTION_ALIASES.items():
        if any(alias in key for alias in aliases) or canonical in key:
            return canonical
    return None


def normalize_goal(value: str | None) -> str | None:
    """Return the canonical goal for a free-form goal string, or ``None``."""
    if not value:
        return None
    key = value.strip().lower()
    for canonical, aliases in _GOAL_ALIASES.items():
        if key == canonical or key in aliases:
            return canonical
    for canonical, aliases in _GOAL_ALIASES.items():
        if any(alias in key for alias in aliases) or canonical in key:
            return canonical
    return None


def _extract_json(raw_response: str) -> str:
    text = raw_response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _extract_json(raw_response: str) -> str:
    text = raw_response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
