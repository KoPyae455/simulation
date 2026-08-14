"""Dependency wiring for replaceable repositories and cognition services."""

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.core.events import InMemoryEventBus
from app.core.llm.service import get_llm_provider
from app.modules.activity.repository import SqliteAgentEventRepository
from app.modules.activity.service import AgentEventService
from app.modules.agent.logs import DecisionLogStore, SqliteDecisionLogRepository
from app.modules.agent.repository import AgentRepository
from app.modules.agent.service import AgentService
from app.modules.cognition.brain_service import BrainService
from app.modules.cognition.brain_state import BrainStateStore
from app.modules.cognition.context_builder import ContextBuilder
from app.modules.cognition.llm_planner import LLMPlanner
from app.modules.cognition.plan_executor import PlanExecutor
from app.modules.cognition.plan_validator import PlanValidator
from app.modules.cognition.planner import RuleBasedPlanner
from app.modules.cognition.planner_service import CompositePlanner
from app.modules.cognition.reflection import ReflectionEngine
from app.modules.memory.repository import SqliteMemoryRepository
from app.modules.memory.service import MemoryService
from app.modules.simulation.service import SimulationService, create_default_simulation_service
from app.modules.world.repository import SqliteWorldRepository
from app.modules.world.service import WorldKnowledgeService, WorldPerceptionService


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
    return create_default_simulation_service(
        get_agent_repository(),
        get_decision_log_repository(),
        get_memory_service(),
        get_brain_service(),
        get_reflection_engine(),
        get_agent_event_service(),
    )


@lru_cache
def get_world_repository() -> SqliteWorldRepository:
    repository = SqliteWorldRepository(_sqlite_path(get_settings().database_url))
    repository.initialize()
    return repository


def get_world_knowledge_service() -> WorldKnowledgeService:
    return WorldKnowledgeService(get_world_repository())


def get_world_perception_service() -> WorldPerceptionService:
    return WorldPerceptionService(get_world_knowledge_service(), get_world_repository())


@lru_cache
def get_memory_repository() -> SqliteMemoryRepository:
    repository = SqliteMemoryRepository(_sqlite_path(get_settings().database_url))
    repository.initialize()
    return repository


@lru_cache
def get_memory_service() -> MemoryService:
    return MemoryService(
        get_memory_repository(),
        InMemoryEventBus(),
        event_service=get_agent_event_service(),
    )


@lru_cache
def get_agent_event_repository() -> SqliteAgentEventRepository:
    """Return the process-local SQLite repository for agent activity events."""
    repository = SqliteAgentEventRepository(_sqlite_path(get_settings().database_url))
    repository.initialize()
    return repository


@lru_cache
def get_agent_event_service() -> AgentEventService:
    """Return the process-local agent activity event service."""
    return AgentEventService(get_agent_event_repository())


@lru_cache
def get_brain_state_store() -> BrainStateStore:
    """Return the process-local brain metadata store (decisions + step cursors)."""
    return BrainStateStore()


@lru_cache
def get_context_builder() -> ContextBuilder:
    """Return the process-local decision-context builder for planners."""
    return ContextBuilder(
        perception=get_world_perception_service(),
        world_repository=get_world_repository(),
        memory_service=get_memory_service(),
    )


@lru_cache
def get_llm_planner() -> LLMPlanner:
    """Return an LLM planner backed by the configured provider (lazy, no connection)."""
    return LLMPlanner(provider=get_llm_provider(), validator=PlanValidator())


@lru_cache
def get_composite_planner() -> CompositePlanner:
    """Return the planner router honoring PLANNER_TYPE and LLM_FALLBACK_TO_RULES."""
    settings = get_settings()
    planner_type = settings.planner_type.lower()
    llm_planner = get_llm_planner() if planner_type == "llm" else None
    return CompositePlanner(
        planner_type=planner_type,
        rule_based_planner=RuleBasedPlanner(),
        llm_planner=llm_planner,
        fallback_to_rules=settings.llm_fallback_to_rules,
        validator=PlanValidator(),
    )


@lru_cache
def get_brain_service() -> BrainService:
    """Return the process-local brain service used by the simulation loop."""
    return BrainService(
        context_builder=get_context_builder(),
        planner=get_composite_planner(),
        executor=PlanExecutor(
            get_world_repository(),
            event_service=get_agent_event_service(),
        ),
        store=get_brain_state_store(),
        event_service=get_agent_event_service(),
    )


@lru_cache
def get_reflection_engine() -> ReflectionEngine:
    """Return the process-local reflection engine using the configured LLM provider."""
    return ReflectionEngine(provider=get_llm_provider())
