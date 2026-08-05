"""Unit tests for no-op cognition pipeline wiring."""

from datetime import UTC, datetime
from uuid import uuid4

from app.modules.cognition.models import CognitionContext
from app.modules.cognition.pipeline import (
    NoOpActionSelector,
    NoOpGoalGenerator,
    NoOpLearningEngine,
    NoOpNeedAnalyzer,
    NoOpPlanner,
    NoOpReflectionEngine,
    NoOpThinkCycle,
)


def test_no_op_think_cycle_returns_an_empty_result() -> None:
    """The skeleton executes its full pipeline without making cognitive decisions."""
    cycle = NoOpThinkCycle(
        need_analyzer=NoOpNeedAnalyzer(),
        goal_generator=NoOpGoalGenerator(),
        planner=NoOpPlanner(),
        action_selector=NoOpActionSelector(),
        reflection_engine=NoOpReflectionEngine(),
        learning_engine=NoOpLearningEngine(),
    )

    result = cycle.run(
        CognitionContext(
            agent_id=uuid4(),
            simulation_datetime=datetime(2040, 1, 1, tzinfo=UTC),
            needs={"hunger": 80},
        )
    )

    assert result.goals == ()
    assert result.plans == ()
    assert result.selected_action is None
    assert result.learning_result.updates == {}
