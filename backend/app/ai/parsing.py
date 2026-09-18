"""Turns a raw LLM text response into a validated AIClassificationResult.

Shared by every real provider (Ollama, OpenAI-compatible) so "how do we not
trust an LLM's output blindly" is written exactly once.
"""
import json
import re

from pydantic import ValidationError

from app.ai.exceptions import AIOutputValidationError
from app.ai.schemas import AIClassificationResult

# Some models wrap JSON in ```json ... ``` fences despite instructions not to.
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def parse_classification_response(raw_text: str) -> AIClassificationResult:
    fence_match = _CODE_FENCE_RE.search(raw_text)
    candidate = fence_match.group(1) if fence_match else raw_text.strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise AIOutputValidationError(f"Provider response was not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise AIOutputValidationError("Provider response JSON was not an object")

    try:
        return AIClassificationResult.model_validate(payload)
    except ValidationError as exc:
        # This is the concrete defense against hallucination: a model claiming
        # a category/priority outside our enums, or omitting a required field,
        # fails here rather than being silently trusted.
        raise AIOutputValidationError(f"Provider response failed schema validation: {exc}") from exc
