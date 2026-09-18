"""The structured contract every AI provider's output must satisfy.

This is the single most important file in the AI layer: it's what turns
"an LLM said some text" into "a value FlowForge's database and business
rules can trust the *shape* of." A provider raising AIOutputValidationError
because a value doesn't fit here is the system working correctly, not a bug.
"""
from pydantic import BaseModel, Field, field_validator

from app.models.request import RequestCategory, RequestPriority


class AIClassificationResult(BaseModel):
    category: RequestCategory
    subcategory: str | None = None
    priority: RequestPriority
    summary: str = Field(min_length=1, max_length=500)
    entities: dict[str, str] = Field(default_factory=dict)

    # A heuristic score, NOT a calibrated statistical probability — see the
    # "IMPORTANT AI DESIGN RULE" in FLOWFORGE_SPEC.md and the confidence
    # section of docs/learning/PHASE_4_AI_PIPELINE.md. An LLM asked to rate
    # its own confidence is not the same thing as a model whose confidence
    # has been measured against known-correct labels. Deterministic
    # validation and business rules (Phase 5), not this number, make the
    # actual business decisions.
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("entities")
    @classmethod
    def cap_entity_count(cls, value: dict[str, str]) -> dict[str, str]:
        # A hallucinating or misbehaving model could return an unbounded
        # number of "entities" — cap it rather than trust it blindly.
        if len(value) > 20:
            raise ValueError("too many entities returned (max 20)")
        return value
