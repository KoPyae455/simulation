"""HTTP controls for manually and automatically advancing the simulation."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.dependencies import get_simulation_service
from app.modules.simulation.models import SimulationStatus, SimulationStepResult
from app.modules.simulation.service import SimulationService

router = APIRouter(prefix="/simulation")


@router.post("/step", response_model=SimulationStepResult)
async def step_simulation(
    service: Annotated[SimulationService, Depends(get_simulation_service)],
) -> SimulationStepResult:
    """Advance world time and all persisted agent needs by one simulation tick."""
    return await service.step()


@router.post("/start", response_model=SimulationStatus)
async def start_simulation(
    service: Annotated[SimulationService, Depends(get_simulation_service)],
) -> SimulationStatus:
    """Start the automatic two-second simulation loop."""
    return await service.start()


@router.post("/stop", response_model=SimulationStatus)
async def stop_simulation(
    service: Annotated[SimulationService, Depends(get_simulation_service)],
) -> SimulationStatus:
    """Stop the automatic simulation loop."""
    return await service.stop()
