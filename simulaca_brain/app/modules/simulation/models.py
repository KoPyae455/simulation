"""Application models returned by simulation controls."""

from datetime import datetime

from app.core.schemas import SimulacaBaseModel


from app.modules.agent.models import PlanStep


class SimulationStatus(SimulacaBaseModel):
    """Current lifecycle and time state of the simulation engine."""

    current_tick: int
    current_simulation_datetime: datetime
    is_running: bool
    current_goal: str | None = None
    current_action: str | None = None
    current_plan: list[PlanStep] | None = None


class SimulationStepResult(SimulationStatus):
    """Result of one completed simulation step."""

    agents_updated: int
