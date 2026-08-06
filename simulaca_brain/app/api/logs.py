"""HTTP endpoints for inspecting and clearing agent decision history."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import get_decision_log_repository
from app.modules.agent.logs import AgentDecisionLog, DecisionLogStore

router = APIRouter(prefix="/logs")


@router.get("", response_model=list[AgentDecisionLog])
async def list_decision_logs(
    repository: Annotated[DecisionLogStore, Depends(get_decision_log_repository)],
    agent_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[AgentDecisionLog]:
    """Return recent decision history, optionally for one agent."""
    return repository.list(agent_id=agent_id, limit=limit)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_decision_logs(
    repository: Annotated[DecisionLogStore, Depends(get_decision_log_repository)],
) -> None:
    """Clear stored decision history for the developer dashboard."""
    repository.clear()
