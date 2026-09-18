"""Any provider speaking the OpenAI chat-completions REST format — OpenAI
itself, or a compatible endpoint (many hosted and self-hosted LLM servers
implement this same API shape) — selected purely via environment variables,
per FLOWFORGE_SPEC.md's "OpenAI-compatible API through environment
variables" requirement. No vendor-specific SDK: a plain HTTP POST is enough
and keeps this provider usable against anything compatible, not just OpenAI.
"""
import httpx

from app.ai.base import AIProvider
from app.ai.exceptions import AIProviderError
from app.ai.parsing import parse_classification_response
from app.ai.prompts import SYSTEM_PROMPT, build_user_prompt
from app.ai.schemas import AIClassificationResult


class OpenAICompatibleProvider(AIProvider):
    def __init__(self, base_url: str, api_key: str, model: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds

    def classify(self, title: str, description: str) -> AIClassificationResult:
        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": build_user_prompt(title, description)},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                },
                timeout=self._timeout_seconds,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AIProviderError(f"OpenAI-compatible request failed: {exc}") from exc

        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, ValueError) as exc:
            raise AIProviderError(f"Unexpected OpenAI-compatible response shape: {exc}") from exc

        return parse_classification_response(content)
