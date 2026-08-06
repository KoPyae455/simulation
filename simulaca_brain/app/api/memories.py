"""HTTP endpoints for agent memory operations."""

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from pydantic import Field

from app.api.dependencies import get_memory_service
from app.modules.memory.models import CreateMemoryRequest, MemorySummary, MemoryType
from app.modules.memory.service import MemoryService
from app.core.schemas import SimulacaBaseModel

router = APIRouter(prefix="/agents")


class CreateAgentMemoryRequest(SimulacaBaseModel):
    """Request body for persisting a new memory record for an agent."""

    memory_type: MemoryType
    content: str = Field(min_length=1)
    attributes: dict[str, Any] = Field(default_factory=dict)


@router.get("/{agent_id}/memories", response_model=list[MemorySummary])
async def list_agent_memories(
    agent_id: UUID,
    service: Annotated[MemoryService, Depends(get_memory_service)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[MemorySummary]:
    """Return the newest memories for one agent."""
    memories = service.list_memories(agent_id=agent_id, limit=limit)
    return [MemorySummary(**memory.model_dump()) for memory in memories]


@router.post("/{agent_id}/memories", response_model=MemorySummary, status_code=status.HTTP_201_CREATED)
async def create_agent_memory(
    agent_id: UUID,
    request: CreateAgentMemoryRequest,
    service: Annotated[MemoryService, Depends(get_memory_service)],
) -> MemorySummary:
    """Persist a new memory record for an agent."""
    memory = service.record(
        CreateMemoryRequest(agent_id=agent_id, **request.model_dump())
    )
    return MemorySummary(**memory.model_dump())


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_memory(
    memory_id: UUID,
    service: Annotated[MemoryService, Depends(get_memory_service)],
) -> None:
    """Delete a specific memory record."""
    service.delete_memory(memory_id)
