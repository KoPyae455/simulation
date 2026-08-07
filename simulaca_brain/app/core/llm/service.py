"""Factory for configured LLM providers."""

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.core.llm.base import LLMProvider
from app.core.llm.ollama import OllamaProvider


def create_llm_provider(settings: Settings | None = None) -> LLMProvider:
    """Build the configured LLM provider without hard-coding a backend."""
    config = settings or get_settings()
    provider_name = config.llm_provider.lower()
    base_url = config.llm_base_url or config.ollama_base_url

    if provider_name == "ollama":
        return OllamaProvider(
            base_url=base_url,
            model=config.llm_model,
            timeout_seconds=config.llm_timeout_seconds,
        )

    raise ValueError(f"Unsupported LLM provider '{config.llm_provider}'.")


@lru_cache
def get_llm_provider() -> LLMProvider:
    """Return the process-wide LLM provider singleton."""
    return create_llm_provider()
