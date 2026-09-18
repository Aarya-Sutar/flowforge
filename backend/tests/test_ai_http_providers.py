"""Tests OllamaProvider and OpenAICompatibleProvider against a mocked HTTP
layer — no real network calls, no real Ollama/OpenAI server required. This is
exactly the "testing without real AI APIs" requirement from FLOWFORGE_SPEC.md
Phase 4, applied to the two real providers rather than just the mock one."""
import httpx
import pytest

from app.ai.exceptions import AIOutputValidationError, AIProviderError
from app.ai.providers.ollama import OllamaProvider
from app.ai.providers.openai_compatible import OpenAICompatibleProvider


class FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=self)

    def json(self) -> dict:
        return self._json_data


VALID_CLASSIFICATION_JSON = (
    '{"category": "IT_SUPPORT", "priority": "HIGH", "summary": "Cannot access repo", '
    '"confidence": 0.9, "entities": {"system": "git"}}'
)


class TestOllamaProvider:
    def test_classify_parses_valid_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(url, json, timeout):
            assert url.endswith("/api/chat")
            assert json["format"] == "json"
            return FakeResponse({"message": {"content": VALID_CLASSIFICATION_JSON}})

        monkeypatch.setattr("app.ai.providers.ollama.httpx.post", fake_post)

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3:8b")
        result = provider.classify("title", "description")

        assert result.category.value == "IT_SUPPORT"

    def test_classify_raises_ai_provider_error_on_connection_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(url, json, timeout):
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr("app.ai.providers.ollama.httpx.post", fake_post)

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3:8b")
        with pytest.raises(AIProviderError):
            provider.classify("title", "description")

    def test_classify_raises_validation_error_on_malformed_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(url, json, timeout):
            return FakeResponse({"message": {"content": "not json at all"}})

        monkeypatch.setattr("app.ai.providers.ollama.httpx.post", fake_post)

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3:8b")
        with pytest.raises(AIOutputValidationError):
            provider.classify("title", "description")

    def test_classify_raises_provider_error_on_unexpected_response_shape(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(url, json, timeout):
            return FakeResponse({"unexpected": "shape"})

        monkeypatch.setattr("app.ai.providers.ollama.httpx.post", fake_post)

        provider = OllamaProvider(base_url="http://localhost:11434", model="llama3:8b")
        with pytest.raises(AIProviderError):
            provider.classify("title", "description")


class TestOpenAICompatibleProvider:
    def test_classify_parses_valid_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(url, headers, json, timeout):
            assert url.endswith("/chat/completions")
            assert headers["Authorization"] == "Bearer test-key"
            return FakeResponse({"choices": [{"message": {"content": VALID_CLASSIFICATION_JSON}}]})

        monkeypatch.setattr("app.ai.providers.openai_compatible.httpx.post", fake_post)

        provider = OpenAICompatibleProvider(base_url="https://api.openai.com/v1", api_key="test-key", model="gpt-4o-mini")
        result = provider.classify("title", "description")

        assert result.category.value == "IT_SUPPORT"
        assert result.entities == {"system": "git"}

    def test_classify_raises_ai_provider_error_on_http_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(url, headers, json, timeout):
            return FakeResponse({}, status_code=401)

        monkeypatch.setattr("app.ai.providers.openai_compatible.httpx.post", fake_post)

        provider = OpenAICompatibleProvider(base_url="https://api.openai.com/v1", api_key="bad-key", model="gpt-4o-mini")
        with pytest.raises(AIProviderError):
            provider.classify("title", "description")
