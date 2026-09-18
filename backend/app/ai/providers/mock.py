"""Deterministic, dependency-free provider. Default provider (AI_PROVIDER=mock)
so the app and test suite work with no API key and no local LLM at all — per
FLOWFORGE_SPEC.md: "The application must also work in test mode without
requiring a paid external LLM."

This is keyword matching, not machine learning. Its "confidence" values are
fixed constants chosen to *look* plausible, not measured against anything —
an even more blunt version of the same warning that applies to real LLM
self-reported confidence (see app/ai/schemas.py). Never mistake this for a
real classifier; it exists purely to exercise the pipeline deterministically.
"""
import re

from app.ai.base import AIProvider
from app.ai.schemas import AIClassificationResult
from app.models.request import RequestCategory, RequestPriority

# Matches "$1,200", "$1200.50", "1200 dollars" — deliberately simple, not a
# general-purpose money parser.
_AMOUNT_RE = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)|([\d,]+(?:\.\d+)?)\s?dollars")

_CATEGORY_KEYWORDS: list[tuple[RequestCategory, tuple[str, ...]]] = [
    (RequestCategory.ACCESS_REQUEST, ("access", "permission", "login", "password", "vpn", "locked out")),
    (RequestCategory.IT_SUPPORT, ("laptop", "computer", "software", "network", "git", "repository", "server", "wifi")),
    (RequestCategory.HR, ("payroll", "salary", "leave", "vacation", "onboarding", "benefits", "hr")),
    (RequestCategory.FINANCE, ("invoice", "budget", "expense", "reimbursement", "payment", "finance")),
    (RequestCategory.PROCUREMENT, ("purchase order", "vendor", "procurement", "supplier", "quote")),
    (RequestCategory.CUSTOMER_SERVICE, ("customer", "complaint", "refund", "client")),
]

_HIGH_PRIORITY_KEYWORDS = ("urgent", "asap", "immediately", "cannot work", "critical", "down", "blocked")


class MockAIProvider(AIProvider):
    def classify(self, title: str, description: str) -> AIClassificationResult:
        text = f"{title} {description}".lower()

        category = self._match_category(text)
        priority = (
            RequestPriority.HIGH if any(kw in text for kw in _HIGH_PRIORITY_KEYWORDS) else RequestPriority.MEDIUM
        )
        confidence = 0.85 if category is not None else 0.4

        return AIClassificationResult(
            category=category or RequestCategory.GENERAL,
            subcategory=None,
            priority=priority,
            summary=self._summarize(title),
            entities=self._extract_entities(text),
            amount=self._extract_amount(text),
            confidence=confidence,
        )

    @staticmethod
    def _match_category(text: str) -> RequestCategory | None:
        for category, keywords in _CATEGORY_KEYWORDS:
            if any(kw in text for kw in keywords):
                return category
        return None

    @staticmethod
    def _summarize(title: str) -> str:
        return title.strip()[:200] or "No summary available"

    @staticmethod
    def _extract_amount(text: str) -> float | None:
        match = _AMOUNT_RE.search(text)
        if not match:
            return None
        raw = (match.group(1) or match.group(2)).replace(",", "")
        return float(raw)

    @staticmethod
    def _extract_entities(text: str) -> dict[str, str]:
        entities: dict[str, str] = {}
        if "git" in text or "repository" in text:
            entities["system"] = "git repository"
        if "vpn" in text:
            entities["system"] = "VPN"
        if "password" in text:
            entities["issue"] = "password"
        return entities
