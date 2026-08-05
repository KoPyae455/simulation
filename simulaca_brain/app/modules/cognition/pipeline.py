"""Interfaces and no-op orchestration for the cognition pipeline."""

from typing import Protocol

from app.modules.cognition.models import (
    CognitionContext,
    Goal,
    LearningResult,
    NeedAssessment,
    Plan,
    Reflection,
    SelectedAction,
    ThinkCycleResult,
)


class NeedAnalyzer(Protocol):
    """Port for assessing which state needs merit attention."""

    def analyze(self, context: CognitionContext) -> NeedAssessment:
        """Produce a need assessment from the supplied state snapshot."""


class GoalGenerator(Protocol):
    """Port for creating candidate goals from assessed needs."""

    def generate(self, context: CognitionContext, assessment: NeedAssessment) -> tuple[Goal, ...]:
        """Generate zero or more goals for the current cycle."""


class Planner(Protocol):
    """Port for producing a candidate plan for an individual goal."""

    def plan(self, context: CognitionContext, goal: Goal) -> Plan:
        """Produce a plan for ``goal`` using the current state snapshot."""


class ActionSelector(Protocol):
    """Port for selecting one action from available plans."""

    def select(self, context: CognitionContext, plans: tuple[Plan, ...]) -> SelectedAction | None:
        """Select an action to execute, or ``None`` when no action is selected."""


class ReflectionEngine(Protocol):
    """Port for evaluating the outcome of a cognition cycle."""

    def reflect(self, context: CognitionContext, action: SelectedAction | None) -> Reflection:
        """Produce reflection data without mutating external state."""


class LearningEngine(Protocol):
    """Port for producing future learning updates from reflection data."""

    def learn(self, context: CognitionContext, reflection: Reflection) -> LearningResult:
        """Produce proposed learning updates without applying them."""


class ThinkCycle(Protocol):
    """Port for executing one complete cognition pipeline cycle."""

    def run(self, context: CognitionContext) -> ThinkCycleResult:
        """Process one cognition snapshot and return an inspectable result."""


class NoOpNeedAnalyzer:
    """Empty need-analysis implementation for wiring the cognition skeleton."""

    def analyze(self, context: CognitionContext) -> NeedAssessment:
        """Return an empty assessment without interpreting needs."""
        return NeedAssessment()


class NoOpGoalGenerator:
    """Empty goal-generation implementation for wiring the cognition skeleton."""

    def generate(self, context: CognitionContext, assessment: NeedAssessment) -> tuple[Goal, ...]:
        """Return no goals without applying goal-generation logic."""
        return ()


class NoOpPlanner:
    """Empty planning implementation for wiring the cognition skeleton."""

    def plan(self, context: CognitionContext, goal: Goal) -> Plan:
        """Return an empty plan for ``goal`` without planning behavior."""
        return Plan(goal=goal)


class NoOpActionSelector:
    """Empty action-selection implementation for wiring the cognition skeleton."""

    def select(self, context: CognitionContext, plans: tuple[Plan, ...]) -> SelectedAction | None:
        """Return no selected action without decision logic."""
        return None


class NoOpReflectionEngine:
    """Empty reflection implementation for wiring the cognition skeleton."""

    def reflect(self, context: CognitionContext, action: SelectedAction | None) -> Reflection:
        """Return empty reflection data without evaluating an action."""
        return Reflection()


class NoOpLearningEngine:
    """Empty learning implementation for wiring the cognition skeleton."""

    def learn(self, context: CognitionContext, reflection: Reflection) -> LearningResult:
        """Return no learning updates without modifying agent knowledge."""
        return LearningResult()


class NoOpThinkCycle:
    """Compose cognition ports into a non-AI, inspectable pipeline execution."""

    def __init__(
        self,
        need_analyzer: NeedAnalyzer,
        goal_generator: GoalGenerator,
        planner: Planner,
        action_selector: ActionSelector,
        reflection_engine: ReflectionEngine,
        learning_engine: LearningEngine,
    ) -> None:
        """Create a pipeline using injected cognition collaborators."""
        self._need_analyzer = need_analyzer
        self._goal_generator = goal_generator
        self._planner = planner
        self._action_selector = action_selector
        self._reflection_engine = reflection_engine
        self._learning_engine = learning_engine

    def run(self, context: CognitionContext) -> ThinkCycleResult:
        """Pass a snapshot through all pipeline stages without AI behavior."""
        assessment = self._need_analyzer.analyze(context)
        goals = self._goal_generator.generate(context, assessment)
        plans = tuple(self._planner.plan(context, goal) for goal in goals)
        selected_action = self._action_selector.select(context, plans)
        reflection = self._reflection_engine.reflect(context, selected_action)
        learning_result = self._learning_engine.learn(context, reflection)
        return ThinkCycleResult(
            need_assessment=assessment,
            goals=goals,
            plans=plans,
            selected_action=selected_action,
            reflection=reflection,
            learning_result=learning_result,
        )
