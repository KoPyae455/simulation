"""Unit tests for the LLM cognitive planner and fallback routing."""

from datetime import UTC, datetime
import json
from uuid import uuid4

import pytest

from app.api import dependencies as brain_dependencies
from app.core.llm.fake import FakeLLMProvider
from app.modules.agent.state import AgentNeeds
from app.modules.cognition.decision_context import DecisionContext
from app.modules.cognition.exceptions import LLMPlanningError
from app.modules.cognition.llm_planner import LLMPlanner
from app.modules.cognition.plan_validator import PlanValidator
from app.modules.cognition.planner import RuleBasedPlanner
from app.modules.cognition.planner_service import CompositePlanner
from app.modules.world.models import Entity, Location


def _build_context() -> DecisionContext:
    home = Location(id=uuid4(), name="Home", description="Alice's house")
    river = Location(id=uuid4(), name="River", description="A flowing river")
    water = Entity(id=uuid4(), name="Water", location_id=river.id, attributes={"drinkable": True})

    return DecisionContext(
        agent_id=uuid4(),
        agent_name="Alice",
        tick=1,
        simulation_datetime=datetime(2024, 1, 1, tzinfo=UTC),
        needs=AgentNeeds(thirst=95),
        current_location=home,
        current_goal="drink",
        nearby_locations=[home, river],
        nearby_entities=[water],
        available_actions=["move", "drink", "eat", "sleep", "idle"],
        action_constraints={"allowed_location_names": ["Home", "River"]},
    )


def _planner(response: str, *, should_timeout: bool = False) -> LLMPlanner:
    provider = FakeLLMProvider(response=response, model="fake-llm", should_timeout=should_timeout)
    return LLMPlanner(provider=provider, validator=PlanValidator())


def _rule_based_plan_steps(context: DecisionContext) -> list[str]:
    planner = RuleBasedPlanner()
    return [step.action for step in planner.plan(context).steps]


def _clear_dependency_caches() -> None:
    brain_dependencies.get_settings.cache_clear()
    brain_dependencies.get_composite_planner.cache_clear()


def test_llm_planner_generates_valid_action_plan() -> None:
    context = _build_context()
    response = json.dumps(
        {
            "goal": "drink",
            "reasoning_summary": "Alice is thirsty and should go to the river.",
            "steps": [
                {"action": "move", "target": "River", "parameters": {}},
                {"action": "drink", "target": "River", "parameters": {}},
            ],
        }
    )

    result = _planner(response).plan(context)

    assert result.status == "success"
    assert result.model == "fake-llm"
    assert result.plan.goal == "drink"
    assert [step.action for step in result.plan.steps] == ["move", "drink"]
    assert [step.target for step in result.plan.steps] == ["River", "River"]


def test_llm_planner_rejects_invalid_json_response() -> None:
    context = _build_context()

    with pytest.raises(LLMPlanningError, match="LLM response was not valid JSON") as exc_info:
        _planner("this is not json").plan(context)

    assert exc_info.value.details == {}


def test_llm_planner_rejects_unknown_action() -> None:
    context = _build_context()
    response = json.dumps(
        {
            "goal": "drink",
            "reasoning_summary": "Alice wants to teleport to the river.",
            "steps": [
                {"action": "teleport", "target": "River", "parameters": {}},
            ],
        }
    )

    with pytest.raises(LLMPlanningError, match="Unknown action 'teleport'") as exc_info:
        _planner(response).plan(context)

    assert exc_info.value.details["error_type"] == "InvalidPlanError"


def test_llm_planner_rejects_unknown_target() -> None:
    context = _build_context()
    response = json.dumps(
        {
            "goal": "drink",
            "reasoning_summary": "Alice tries to move to the moon.",
            "steps": [
                {"action": "move", "target": "Moon", "parameters": {}},
            ],
        }
    )

    with pytest.raises(LLMPlanningError, match="Unknown move target 'Moon'") as exc_info:
        _planner(response).plan(context)

    assert exc_info.value.details["error_type"] == "InvalidPlanError"


def test_llm_planner_wraps_timeout_errors() -> None:
    context = _build_context()

    with pytest.raises(LLMPlanningError, match="Fake LLM timeout") as exc_info:
        _planner("{}", should_timeout=True).plan(context)

    assert exc_info.value.details["error_type"] == "TimeoutError"


def test_composite_planner_falls_back_to_rules_when_env_flag_is_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    context = _build_context()
    fake_llm = _planner("{}", should_timeout=True)

    monkeypatch.setenv("SIMULACA_PLANNER_TYPE", "llm")
    monkeypatch.setenv("SIMULACA_LLM_FALLBACK_TO_RULES", "true")

    _clear_dependency_caches()
    monkeypatch.setattr(brain_dependencies, "get_llm_planner", lambda: fake_llm)

    try:
        composite = brain_dependencies.get_composite_planner()
        outcome = composite.plan(context)
    finally:
        _clear_dependency_caches()

    assert outcome.status == "fallback"
    assert outcome.planner_type == "llm"
    assert outcome.error_type == "LLMPlanningError"
    assert outcome.fallback_reason == "Fake LLM timeout"
    assert [step.action for step in outcome.plan.steps] == _rule_based_plan_steps(context)
