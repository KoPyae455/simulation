"""Parse and validate structured LLM planning responses."""

import json
import re

from pydantic import ValidationError

from app.modules.cognition.action_plan import ActionPlan
from app.modules.cognition.exceptions import LLMPlanningError


def parse_action_plan(raw_response: str) -> ActionPlan:
    """Parse ``raw_response`` into an ``ActionPlan`` or raise ``LLMPlanningError``."""
    payload_text = _extract_json(raw_response)
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise LLMPlanningError("LLM response was not valid JSON.") from exc

    try:
        return ActionPlan.model_validate(payload)
    except ValidationError as exc:
        raise LLMPlanningError("LLM response did not match the ActionPlan schema.") from exc


def _extract_json(raw_response: str) -> str:
    text = raw_response.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()
