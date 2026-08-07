"""Immutable data contracts passed through the cognition pipeline."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class CognitionContext:
    """A point-in-time input snapshot for one agent's cognition cycle."""

    agent_id: UUID
    simulation_datetime: datetime
    needs: Mapping[str, int]
    observations: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NeedAssessment:
    """A normalized view of the agent needs considered during a cycle."""

    urgencies: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Goal:
    """A candidate outcome generated from the current cognition context."""

    identifier: str
    description: str


@dataclass(frozen=True, slots=True)
class PlanStep:
    """A deterministic step inside a candidate plan."""

    action: str
    rationale: str
    priority: int = 1


@dataclass(frozen=True, slots=True)
class Plan:
    """An ordered set of candidate steps for one goal."""

    goal: Goal
    steps: tuple[PlanStep, ...] = ()


@dataclass(frozen=True, slots=True)
class SelectedAction:
    """The action selected for execution by a future agent-actuation component."""

    name: str
    parameters: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Reflection:
    """An evaluation of the cycle outcome reserved for future reflective reasoning."""

    observations: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LearningResult:
    """Proposed learning updates produced without mutating any external module."""

    updates: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ThinkCycleResult:
    """The complete, inspectable output of one cognition pipeline execution."""

    need_assessment: NeedAssessment
    goals: tuple[Goal, ...]
    plans: tuple[Plan, ...]
    selected_action: SelectedAction | None
    reflection: Reflection
    learning_result: LearningResult
