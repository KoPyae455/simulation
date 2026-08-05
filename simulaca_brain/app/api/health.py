"""Liveness endpoint for the Simulaca brain API."""

from fastapi import APIRouter, Depends

from app.core.config import Settings, get_settings
from app.core.schemas import SimulacaBaseModel

router = APIRouter()


class HealthResponse(SimulacaBaseModel):
    """Shape returned by the health check endpoint."""

    status: str
    app_name: str
    app_version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def get_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    """
    Report basic liveness information.

    Deliberately kept free of database/LLM-backend dependencies so it
    stays meaningful even if those subsystems are degraded -- letting
    orchestration tooling tell "process is up" apart from "process is
    fully healthy" once deeper checks are added.
    """
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
        environment=settings.environment.value,
    )