"""HTTP endpoints for creating and inspecting agents."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_agent_service
from app.modules.agent.models import Agent, CreateAgentRequest, UpdateAgentRequest
from app.modules.agent.service import AgentService
from app.modules.world.service import WorldPerceptionService, WorldKnowledgeService
from app.api.dependencies import get_world_perception_service, get_world_knowledge_service

router = APIRouter(prefix="/agents")


@router.post("", response_model=Agent, status_code=status.HTTP_201_CREATED)
async def create_agent(request: CreateAgentRequest, service: Annotated[AgentService, Depends(get_agent_service)]) -> Agent:
    """Create an autonomous agent with normalized basic needs."""
    return service.create_agent(request)


@router.get("", response_model=list[Agent])
async def list_agents(
    service: Annotated[AgentService, Depends(get_agent_service)],
    limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0),
) -> list[Agent]:
    """List agents using bounded offset pagination."""
    return service.list_agents(limit, offset)


@router.get("/{agent_id}", response_model=Agent)
async def get_agent(agent_id: UUID, service: Annotated[AgentService, Depends(get_agent_service)]) -> Agent:
    """Return the current state of one agent."""
    return service.get_agent(agent_id)


@router.patch("/{agent_id}", response_model=Agent)
async def update_agent(
    agent_id: UUID,
    request: UpdateAgentRequest,
    service: Annotated[AgentService, Depends(get_agent_service)],
) -> Agent:
    """Partially update an existing agent after schema and domain validation."""
    return service.update_agent(agent_id, request)


@router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(agent_id: UUID, service: Annotated[AgentService, Depends(get_agent_service)]) -> None:
    """Delete an existing agent."""
    service.delete_agent(agent_id)


@router.get("/{agent_id}/perception", response_model=dict)
def agent_perception(
    agent_id: UUID, perception: Annotated[WorldPerceptionService, Depends(get_world_perception_service)],
) -> dict:
    """Return the selected agent's current perception of the world."""
    return perception.perceive(agent_id)


@router.get("/{agent_id}/context", response_model=dict)
def agent_context(
    agent_id: UUID,
    perception: Annotated[WorldPerceptionService, Depends(get_world_perception_service)],
    knowledge: Annotated[WorldKnowledgeService, Depends(get_world_knowledge_service)],
) -> dict:
    """Return a minimal decision context for the agent combining memory and perception.

    Full DecisionContext will be built later; return perception and basic location info for now.
    """
    p = perception.perceive(agent_id)
    loc = None
    if p.get("location"):
        try:
            loc = knowledge.get_location(UUID(p["location"]))
            loc = loc.model_dump()
        except Exception:
            loc = None
    return {"perception": p, "location": loc}
