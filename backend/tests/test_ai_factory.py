import pytest

from app.ai.factory import get_ai_provider
from app.ai.providers.mock import MockAIProvider
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.core.config import settings


def test_defaults_to_mock_provider() -> None:
    assert isinstance(get_ai_provider(), MockAIProvider)


def test_returns_ollama_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "ollama")
    assert isinstance(get_ai_provider(), OllamaProvider)


def test_returns_openai_provider_when_key_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "sk-test")
    assert isinstance(get_ai_provider(), OpenAICompatibleProvider)


def test_openai_provider_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError):
        get_ai_provider()


def test_unknown_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "AI_PROVIDER", "carrier-pigeon")
    with pytest.raises(ValueError):
        get_ai_provider()
