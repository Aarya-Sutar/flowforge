"""Exceptions the AI layer raises. Both are treated as retryable by the Celery
task (see app/workers/tasks.py) — a network blip and a one-off malformed
response are both plausibly transient for a nondeterministic LLM."""


class AIProviderError(Exception):
    """The provider couldn't be reached, timed out, or returned an HTTP error —
    a network/infrastructure failure, not a problem with what it said."""


class AIOutputValidationError(Exception):
    """The provider responded, but what it said wasn't valid: not parseable as
    JSON, missing required fields, or containing values outside what
    FlowForge's schema allows (e.g. a category that doesn't exist)."""
