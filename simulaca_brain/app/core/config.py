"""
Application configuration.

Centralizes all environment-driven settings behind a single, typed
Settings object. Every other module should depend on this instead of
reading os.environ directly, so configuration stays testable and
overridable (e.g. swapping Settings via dependency overrides in tests).
"""

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Deployment environment the application is running in."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Typed application settings, loaded from environment variables
    and/or a .env file.

    Adding a new setting means adding a field here -- nothing else in
    the codebase should reach into os.environ directly.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="SIMULACA_",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application metadata ---
    app_name: str = "Simulaca Brain"
    app_version: str = "0.1.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    # --- API ---
    api_prefix: str = "/api/v1"

    # --- Persistence ---
    database_url: str = "sqlite:///./data/simulaca.db"

    # --- Logging ---
    log_level: str = "INFO"

    # --- LLM backends (consumed once the cognition module lands) ---
    ollama_base_url: str = "http://localhost:11434"
    vllm_base_url: str = "http://localhost:8001"

    # --- Active LLM provider (drives app.core.llm.service.create_llm_provider) ---
    # Env: SIMULACA_LLM_PROVIDER, SIMULACA_LLM_MODEL, SIMULACA_LLM_BASE_URL,
    #      SIMULACA_LLM_TIMEOUT_SECONDS
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2:latest"
    llm_base_url: str | None = None
    llm_timeout_seconds: float = 10.0

    # --- Cognition planner routing ---
    # Env: SIMULACA_PLANNER_TYPE ("llm" or "rules"), SIMULACA_LLM_FALLBACK_TO_RULES
    planner_type: str = "rules"
    llm_fallback_to_rules: bool = True

    @property
    def effective_llm_base_url(self) -> str:
        """Return the base URL used by the configured LLM provider."""
        return self.llm_base_url or self.ollama_base_url

    @property
    def is_production(self) -> bool:
        """Whether the app is running in a production environment."""
        return self.environment is Environment.PRODUCTION


@lru_cache
def get_settings() -> Settings:
    """
    Return the process-wide Settings singleton.

    Cached so Settings is parsed once per process. Routes and services
    pull it via `Depends(get_settings)` rather than importing a global,
    which keeps configuration overridable in tests.
    """
    return Settings()