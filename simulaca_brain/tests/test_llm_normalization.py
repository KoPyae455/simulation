"""Unit tests for the LLM action/goal normalization layer."""

import json
from uuid import uuid4

from app.modules.cognition.action_plan import ActionPlan, ActionPlanStep
from app.modules.cognition.llm_response_parser import (
    normalize_action,
    normalize_action_plan,
    normalize_goal,
    parse_action_plan,
)


def test_normalize_action_maps_human_readable_variants():
    assert normalize_action("go to river") == "move"
    assert normalize_action("Move -> River") == "move"
    assert normalize_action("walk to the river") == "move"
    assert normalize_action("travel to River") == "move"

    assert normalize_action("drink water") == "drink"
    assert normalize_action("drink at the river") == "drink"
    assert normalize_action("hydrate") == "drink"

    assert normalize_action("eat food") == "eat"
    assert normalize_action("consume") == "eat"

    assert normalize_action("rest") == "sleep"
    assert normalize_action("take a nap") == "sleep"

    assert normalize_action("wait") == "idle"
    assert normalize_action("do nothing") == "idle"


def test_normalize_action_returns_none_for_unknown():
    assert normalize_action("teleport") is None
    assert normalize_action("dance") is None
    assert normalize_action(None) is None


def test_normalize_goal_maps_variants():
    assert normalize_goal("thirst") == "drink"
    assert normalize_goal("drink water") == "drink"
    assert normalize_goal("hunger") == "eat"
    assert normalize_goal("fatigue") == "sleep"
    assert normalize_goal("none") == "idle"
    assert normalize_goal("drink") == "drink"


def test_parse_action_plan_normalizes_steps_and_goal():
    raw = json.dumps({
        "goal": "thirst",
        "reasoning_summary": "Alice is thirsty.",
        "steps": [
            {"action": "go to river", "target": "River"},
            {"action": "drink water", "target": "River"},
        ],
    })

    plan = parse_action_plan(raw)

    assert plan.goal == "drink"
    assert [step.action for step in plan.steps] == ["move", "drink"]
    assert [step.target for step in plan.steps] == ["River", "River"]


def test_normalize_action_plan_preserves_unmappable_action():
    plan = ActionPlan(
        plan_id=uuid4(),
        goal="drink",
        reasoning_summary="",
        steps=[ActionPlanStep(action="teleport", target="River")],
    )

    normalized = normalize_action_plan(plan)
    assert normalized.steps[0].action == "teleport"  # left for validator to reject
