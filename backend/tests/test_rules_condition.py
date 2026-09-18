import pytest

from app.models.request import RequestCategory, RequestPriority
from app.rules.condition import evaluate_condition
from app.rules.exceptions import RuleParseError


def test_simple_equality_on_enum_field() -> None:
    context = {"category": RequestCategory.ACCESS_REQUEST}
    assert evaluate_condition("category == ACCESS_REQUEST", context) is True
    assert evaluate_condition("category == FINANCE", context) is False


def test_numeric_comparison() -> None:
    context = {"confidence": 0.85}
    assert evaluate_condition("confidence >= 0.80", context) is True
    assert evaluate_condition("confidence < 0.70", context) is False


def test_and_combinator_requires_all_clauses() -> None:
    context = {"category": RequestCategory.ACCESS_REQUEST, "confidence": 0.9}
    assert evaluate_condition("category == ACCESS_REQUEST AND confidence >= 0.80", context) is True

    context2 = {"category": RequestCategory.ACCESS_REQUEST, "confidence": 0.5}
    assert evaluate_condition("category == ACCESS_REQUEST AND confidence >= 0.80", context2) is False


def test_is_null_matches_missing_value() -> None:
    assert evaluate_condition("amount IS NULL", {"amount": None}) is True
    assert evaluate_condition("amount IS NULL", {"amount": 500.0}) is False


def test_is_not_null_matches_present_value() -> None:
    assert evaluate_condition("amount IS NOT NULL", {"amount": 500.0}) is True
    assert evaluate_condition("amount IS NOT NULL", {"amount": None}) is False


def test_null_actual_never_satisfies_comparison_operator() -> None:
    # This is what makes "amount IS NULL" the correct way to express "missing
    # information" rather than e.g. "amount > 100000" happening to pass.
    assert evaluate_condition("amount > 100000", {"amount": None}) is False


def test_finance_amount_threshold_example_from_spec() -> None:
    context = {"category": RequestCategory.FINANCE, "amount": 150000.0}
    assert evaluate_condition("category == FINANCE AND amount > 100000", context) is True

    context2 = {"category": RequestCategory.FINANCE, "amount": 50000.0}
    assert evaluate_condition("category == FINANCE AND amount > 100000", context2) is False


def test_unknown_field_raises() -> None:
    with pytest.raises(RuleParseError):
        evaluate_condition("not_a_real_field == X", {})


def test_unparseable_clause_raises() -> None:
    with pytest.raises(RuleParseError):
        evaluate_condition("category !! FINANCE", {})


def test_non_numeric_value_for_numeric_field_raises() -> None:
    with pytest.raises(RuleParseError):
        evaluate_condition("confidence >= high", {"confidence": 0.9})


def test_priority_field() -> None:
    assert evaluate_condition("priority == HIGH", {"priority": RequestPriority.HIGH}) is True
