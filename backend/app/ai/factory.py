"""Reads AI_PROVIDER and returns the matching provider instance. This function
is the one place that knows all three providers exist — everything else
(processing_service, tests) only ever depends on the AIProvider interface."""
from app.ai.base import AIProvider
from app.ai.providers.mock import MockAIProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import settings


def get_ai_provider() -> AIProvider:
    provider = settings.AI_PROVIDER.lower()

    if provider == "mock":
        return MockAIProvider()

    if provider == "ollama":
        return OllamaProvider(base_url=settings.OLLAMA_BASE_URL, model=settings.OLLAMA_MODEL)

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("AI_PROVIDER=openai requires OPENAI_API_KEY to be set")
        return OpenAICompatibleProvider(
            base_url=settings.OPENAI_BASE_URL,
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_MODEL,
        )

    raise ValueError(f"Unknown AI_PROVIDER: {settings.AI_PROVIDER!r} (expected mock, ollama, or openai)")
