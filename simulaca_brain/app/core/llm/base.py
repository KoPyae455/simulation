"""LLM provider abstraction."""

from typing import Protocol


class LLMProvider(Protocol):
    """Port for generating text completions from a prompt."""

    @property
    def model(self) -> str:
        """Return the configured model identifier."""

    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        """Return the provider's text completion for ``prompt``."""
