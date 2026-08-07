"""Structured action plans produced by planners and consumed by the executor."""

from typing import Any
from uuid import UUID, uuid4

from pydantic import Field

from app.core.schemas import SimulacaBaseModel


class ActionPlanStep(SimulacaBaseModel):
    """One executable step inside an action plan."""

    action: str
    target: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ActionPlan(SimulacaBaseModel):
    """An ordered set of steps proposed to satisfy one goal."""

    plan_id: UUID = Field(default_factory=uuid4)
    goal: str
    reasoning_summary: str = ""
    steps: list[ActionPlanStep] = Field(default_factory=list)
