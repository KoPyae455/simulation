"""HTTP endpoints exposing brain status and per-agent decision/plan metadata.

Only client-safe metadata is returned: planner, model, goal, plan steps,
status, latency, fallback status, and a short reasoning summary. Internal
prompts and chain-of-thought are never exposed.
"""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_brain_service, get_brain_state_store
from app.core.config import Settings, get_settings
from app.core.llm.service import get_llm_provider
from app.core.schemas import SimulacaBaseModel
from app.modules.cognition.brain_service import BrainService
from app.modules.cognition.brain_state import BrainStateStore

router = APIRouter()


class BrainStatusResponse(SimulacaBaseModel):
    """Aggregate brain configuration and runtime state for the dashboard."""

    planner: str
    model: str | None = None
    provider: str | None = None
    fallback_to_rules: bool = True
    llm_available: bool | None = None
    decisions: list[dict[str, Any]] = []
    latest_llm_request: dict[str, Any] | None = None


class AgentDecisionResponse(SimulacaBaseModel):
    """Latest decision metadata for one agent (client-safe fields only)."""

    details: dict[str, Any]


class AgentPlanResponse(SimulacaBaseModel):
    """Latest generated ActionPlan for one agent."""

    plan: dict[str, Any] | None = None


class DecisionNotFoundError(HTTPException):
    """Raised when an agent has no recorded decision yet."""

    def __init__(self, agent_id: UUID) -> None:
        super().__init__(
            status_code=404,
            detail=f"No decision recorded yet for agent '{agent_id}'.",
        )


@router.get("/brain/status", response_model=BrainStatusResponse)
def brain_status(
    store: Annotated[BrainStateStore, Depends(get_brain_state_store)],
    brain: Annotated[BrainService, Depends(get_brain_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> BrainStatusResponse:
    """Return the brain planner configuration and recent decision metadata."""
    model: str | None = None
    provider: str | None = None
    llm_available: bool | None = None
    if settings.planner_type.lower() == "llm":
        provider = settings.llm_provider
        try:
            provider_client = get_llm_provider()
            model = provider_client.model
            llm_available = bool(provider_client.is_available())
        except Exception:
            model = settings.llm_model
            llm_available = None

    latest = store.latest_llm_request()
    return BrainStatusResponse(
        planner=settings.planner_type.lower(),
        model=model,
        provider=provider,
        fallback_to_rules=settings.llm_fallback_to_rules,
        llm_available=llm_available,
        decisions=[decision.to_public_dict() for decision in store.all_decisions()],
        latest_llm_request=asdict(latest) if latest is not None else None,
    )


@router.get("/agents/{agent_id}/decision", response_model=AgentDecisionResponse)
def agent_decision(
    agent_id: UUID,
    store: Annotated[BrainStateStore, Depends(get_brain_state_store)],
) -> AgentDecisionResponse:
    """Return the latest decision metadata for one agent."""
    decision = store.get_decision(agent_id)
    if decision is None:
        raise DecisionNotFoundError(agent_id)
    return AgentDecisionResponse(details=decision.to_public_dict())


@router.get("/agents/{agent_id}/plan", response_model=AgentPlanResponse)
def agent_plan(
    agent_id: UUID,
    store: Annotated[BrainStateStore, Depends(get_brain_state_store)],
) -> AgentPlanResponse:
    """Return the latest validated ActionPlan for one agent."""
    decision = store.get_decision(agent_id)
    if decision is None or decision.plan is None:
        raise DecisionNotFoundError(agent_id)
    plan_payload = decision.to_public_dict()["plan"]
    return AgentPlanResponse(plan=plan_payload)