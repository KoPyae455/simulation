"""Test double that returns deterministic LLM responses."""

from collections.abc import Callable


class FakeLLMProvider:
    """Configurable provider for unit tests without a live LLM server."""

    def __init__(
        self,
        response: str,
        *,
        model: str = "fake-model",
        on_generate: Callable[[str, str | None], None] | None = None,
        should_timeout: bool = False,
        should_fail: bool = False,
    ) -> None:
        self._response = response
        self._model = model
        self._on_generate = on_generate
        self.should_timeout = should_timeout
        self.should_fail = should_fail
        self.last_prompt: str | None = None
        self.last_system_prompt: str | None = None

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        if self._on_generate is not None:
            self._on_generate(prompt, system_prompt)
        if self.should_fail:
            raise RuntimeError("Fake LLM failure")
        if self.should_timeout:
            raise TimeoutError("Fake LLM timeout")
        return self._response

    def is_available(self) -> bool:
        return not self.should_fail
