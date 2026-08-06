"""Application models returned by simulation controls."""

from datetime import datetime

from app.core.schemas import SimulacaBaseModel


class SimulationStatus(SimulacaBaseModel):
    """Current lifecycle and time state of the simulation engine."""

    current_tick: int
    current_simulation_datetime: datetime
    is_running: bool


class SimulationStepResult(SimulationStatus):
    """Result of one completed simulation step."""

    agents_updated: int
