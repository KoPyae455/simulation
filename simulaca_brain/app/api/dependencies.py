"""Dependency wiring for replaceable repositories and cognition services."""

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.modules.agent.logs import DecisionLogStore, SqliteDecisionLogRepository
from app.modules.agent.repository import AgentRepository
from app.modules.agent.service import AgentService
from app.modules.simulation.service import SimulationService, create_default_simulation_service


def _sqlite_path(database_url: str) -> Path:
    if not database_url.startswith("sqlite:///"):
        raise ValueError("Only SQLite database URLs are supported in this release.")
    return Path(database_url.removeprefix("sqlite:///"))


@lru_cache
def get_agent_repository() -> AgentRepository:
    repository = AgentRepository(_sqlite_path(get_settings().database_url))
    repository.initialize()
    return repository


def get_agent_service() -> AgentService:
    return AgentService(get_agent_repository())


@lru_cache
def get_decision_log_repository() -> SqliteDecisionLogRepository:
    """Return the process-local repository for persistent simulation decision logs."""
    repository = SqliteDecisionLogRepository(_sqlite_path(get_settings().database_url))
    repository.initialize()
    return repository


@lru_cache
def get_simulation_service() -> SimulationService:
    """Return the process-local simulation coordinator and its background-loop state."""
    return create_default_simulation_service(get_agent_repository(), get_decision_log_repository())
