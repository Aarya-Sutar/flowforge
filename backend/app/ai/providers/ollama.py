"""Local LLM provider via Ollama (https://ollama.com) — runs entirely on the
developer's machine, no API key, no per-call cost. Used for local development
against a real (if smaller/less capable) model instead of the mock provider.
"""
import httpx

from app.ai.base import AIProvider
from app.ai.exceptions import AIProviderError
from app.ai.parsing import parse_classification_response
from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas import AIClassificationResult


class OllamaProvider(AIProvider):
    def __init__(self, base_url: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds

    def classify(self, title: str, description: str) -> AIClassificationResult:
        try:
            response = httpx.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(title, description)},
                    ],
                    # Ollama's structured-output mode: constrains the model's
                    # output to syntactically valid JSON. Does NOT guarantee the
                    # JSON matches *our* schema — parse_classification_response
                    # still validates that separately.
                    "format": "json",
                    "stream": False,
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Ollama request failed: {exc}") from exc

        try:
            content = response.json()["message"]["content"]
        except (KeyError, ValueError) as exc:
            raise AIProviderError(f"Unexpected Ollama response shape: {exc}") from exc

        return parse_classification_response(content)
