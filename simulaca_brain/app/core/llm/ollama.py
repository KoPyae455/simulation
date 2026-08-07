"""Ollama-backed LLM provider."""

import httpx

from app.core.exceptions import SimulacaError


class OllamaProviderError(SimulacaError):
    """Raised when Ollama returns an error or is unreachable."""

    error_code = "ollama_provider_error"
    http_status = 502


class OllamaProvider:
    """Generate completions through a configured Ollama HTTP endpoint."""

    def __init__(self, *, base_url: str, model: str, timeout_seconds: float) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    @property
    def model(self) -> str:
        return self._model

    def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        payload: dict[str, object] = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.post(f"{self._base_url}/api/generate", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise OllamaProviderError("Ollama request timed out.") from exc
        except httpx.HTTPError as exc:
            raise OllamaProviderError("Ollama is unavailable.") from exc

        content = data.get("response")
        if not isinstance(content, str) or not content.strip():
            raise OllamaProviderError("Ollama returned an empty response.")
        return content

    def is_available(self) -> bool:
        """Return whether the Ollama server responds to a health probe."""
        try:
            with httpx.Client(timeout=min(self._timeout_seconds, 2.0)) as client:
                response = client.get(f"{self._base_url}/api/tags")
                response.raise_for_status()
            return True
        except httpx.HTTPError:
            return False
