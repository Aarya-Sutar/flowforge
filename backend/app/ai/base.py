"""The provider interface. Every provider — mock, Ollama, OpenAI-compatible —
implements exactly this, so app/services/processing_service.py never needs to
know which one it's talking to."""
from abc import ABC, abstractmethod

from app.ai.schemas import AIClassificationResult


class AIProvider(ABC):
    @abstractmethod
    def classify(self, title: str, description: str) -> AIClassificationResult:
        """Classify a request. Raises AIProviderError (network/infra) or
        AIOutputValidationError (bad output) on failure — never returns a
        partially-valid or unvalidated result."""
        raise NotImplementedError
