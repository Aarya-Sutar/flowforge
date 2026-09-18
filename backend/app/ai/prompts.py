"""Builds the prompt sent to a real LLM provider. Both OllamaProvider and
OpenAICompatibleProvider share this — the prompt is provider-agnostic; only
how it's transported (which HTTP endpoint, which request shape) differs.
"""
from app.models.request import RequestCategory, RequestPriority

_CATEGORIES = ", ".join(c.value for c in RequestCategory)
_PRIORITIES = ", ".join(p.value for p in RequestPriority)

SYSTEM_PROMPT = f"""You are a classification engine for an internal business request \
system. You are given a request's title and description. Respond with ONLY a single \
JSON object — no prose, no markdown code fences, nothing before or after it.

The JSON object must have exactly these fields:
- "category": one of [{_CATEGORIES}]
- "subcategory": a short free-text label, or null
- "priority": one of [{_PRIORITIES}]
- "summary": a one-sentence summary of the request, under 200 characters
- "entities": an object of short key/value pairs extracted from the text \
(e.g. {{"system": "internal git repository"}}). Use an empty object {{}} if none apply.
- "confidence": your confidence in this classification, a number from 0.0 to 1.0

Only use information present in the request. Do not invent details that \
were not stated."""


def build_user_prompt(title: str, description: str) -> str:
    return f"Title: {title}\n\nDescription: {description}"
