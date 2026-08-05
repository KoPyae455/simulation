"""HTTP endpoints for creating and inspecting agents."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_agent_service
from app.modules.agent.models import Agent, CreateAgentRequest, UpdateAgentRequest
from app.modules.agent.service import AgentService

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
