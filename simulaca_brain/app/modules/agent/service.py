"""Application service for agent lifecycle operations."""

from uuid import UUID

from app.modules.agent.models import Agent, CreateAgentRequest, UpdateAgentRequest
from app.modules.agent.repository import AgentRepository


class AgentService:
    """Coordinates agent use cases without knowing HTTP details."""

    def __init__(self, repository: AgentRepository) -> None:
        self._repository = repository

    def create_agent(self, request: CreateAgentRequest) -> Agent:
        return self._repository.create(request)

    def get_agent(self, agent_id: UUID) -> Agent:
        return self._repository.get(agent_id)

    def list_agents(self, limit: int, offset: int) -> list[Agent]:
        return self._repository.list(limit, offset)

    def update_agent(self, agent_id: UUID, request: UpdateAgentRequest) -> Agent:
        return self._repository.update(agent_id, request)

    def delete_agent(self, agent_id: UUID) -> None:
        self._repository.delete(agent_id)
