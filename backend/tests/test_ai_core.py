"""Tests for the provider-agnostic parts of the AI layer: the schema contract,
response parsing/validation, and the deterministic mock provider."""
import pytest
from pydantic import ValidationError

from app.ai.exceptions import AIOutputValidationError
from app.ai.parsing import parse_classification_response
from app.ai.providers.mock import MockAIProvider
from app.ai.schemas import AIClassificationResult
from app.models.request import RequestCategory, RequestPriority


def test_ai_classification_result_rejects_unknown_category() -> None:
    with pytest.raises(ValidationError):
        AIClassificationResult(
            category="NOT_A_REAL_CATEGORY",
            priority=RequestPriority.LOW,
            summary="x",
            confidence=0.5,
        )


def test_ai_classification_result_rejects_out_of_range_confidence() -> None:
    with pytest.raises(ValidationError):
        AIClassificationResult(
            category=RequestCategory.GENERAL,
            priority=RequestPriority.LOW,
            summary="x",
            confidence=1.5,
        )


def test_ai_classification_result_caps_entity_count() -> None:
    with pytest.raises(ValidationError):
        AIClassificationResult(
            category=RequestCategory.GENERAL,
            priority=RequestPriority.LOW,
            summary="x",
            confidence=0.5,
            entities={f"k{i}": "v" for i in range(21)},
        )


def test_parse_classification_response_accepts_clean_json() -> None:
    raw = '{"category": "HR", "priority": "LOW", "summary": "test", "confidence": 0.7, "entities": {}}'
    result = parse_classification_response(raw)
    assert result.category == RequestCategory.HR


def test_parse_classification_response_strips_markdown_fences() -> None:
    raw = '```json\n{"category": "HR", "priority": "LOW", "summary": "test", "confidence": 0.7}\n```'
    result = parse_classification_response(raw)
    assert result.category == RequestCategory.HR


def test_parse_classification_response_rejects_non_json() -> None:
    with pytest.raises(AIOutputValidationError):
        parse_classification_response("Sure! This request is about HR stuff.")


def test_parse_classification_response_rejects_hallucinated_category() -> None:
    raw = '{"category": "SECURITY_BREACH", "priority": "HIGH", "summary": "x", "confidence": 0.9}'
    with pytest.raises(AIOutputValidationError):
        parse_classification_response(raw)


def test_parse_classification_response_rejects_missing_required_field() -> None:
    raw = '{"category": "HR", "summary": "test", "confidence": 0.7}'  # no priority
    with pytest.raises(AIOutputValidationError):
        parse_classification_response(raw)


class TestMockProvider:
    def test_is_deterministic(self) -> None:
        provider = MockAIProvider()
        a = provider.classify("Cannot access repo", "I need VPN access")
        b = provider.classify("Cannot access repo", "I need VPN access")
        assert a == b

    def test_classifies_access_keywords_as_access_request(self) -> None:
        provider = MockAIProvider()
        result = provider.classify("Locked out", "I forgot my password and cannot log in")
        assert result.category == RequestCategory.ACCESS_REQUEST

    def test_classifies_hr_keywords(self) -> None:
        provider = MockAIProvider()
        result = provider.classify("Leave request", "I would like to request vacation leave")
        assert result.category == RequestCategory.HR

    def test_defaults_to_general_with_no_keyword_match(self) -> None:
        provider = MockAIProvider()
        result = provider.classify("Random thing", "Nothing matches any keyword here")
        assert result.category == RequestCategory.GENERAL
        assert result.confidence < 0.85  # honest: no match found, lower heuristic score

    def test_urgent_keyword_sets_high_priority(self) -> None:
        provider = MockAIProvider()
        result = provider.classify("System down", "This is urgent, production is blocked")
        assert result.priority == RequestPriority.HIGH

    def test_result_always_passes_schema_validation(self) -> None:
        provider = MockAIProvider()
        result = provider.classify("Anything", "at all, even nonsense zzqx")
        assert isinstance(result, AIClassificationResult)
