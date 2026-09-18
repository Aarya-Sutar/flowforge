"""A small, deliberately restricted condition language for workflow_rules.condition.

Grammar (case-sensitive keywords AND/IS NULL/IS NOT NULL):
    condition := clause (" AND " clause)*
    clause    := FIELD OP VALUE | FIELD "IS NULL" | FIELD "IS NOT NULL"
    OP        := "==" | "!=" | ">=" | "<=" | ">" | "<"

Examples (straight from FLOWFORGE_SPEC.md's rule engine section):
    "category == ACCESS_REQUEST AND confidence >= 0.80"
    "priority == HIGH"
    "confidence < 0.70"
    "category == FINANCE AND amount > 100000"
    "amount IS NULL"

This is intentionally NOT a general-purpose expression language and does not
use eval() or any dynamic code execution — rule text comes from admins via
the API, and arbitrary code execution from stored, user-editable text would
be a real vulnerability. No OR, no parentheses, no nesting: every example in
the spec is a flat AND-of-comparisons, and keeping the grammar this narrow is
what makes every rule easy to read and explain at a glance.
"""
import re

from app.rules.exceptions import RuleParseError

# Numeric fields are compared as floats; every other known field is compared
# as a case-sensitive string (matching the exact enum values stored in the DB).
NUMERIC_FIELDS = {"confidence", "amount"}
KNOWN_FIELDS = {"category", "subcategory", "priority", "confidence", "department", "amount"}

_CLAUSE_RE = re.compile(
    r"^\s*(?P<field>\w+)\s*"
    r"(?:(?P<op>==|!=|>=|<=|>|<)\s*(?P<value>.+?)|(?P<null_op>IS NOT NULL|IS NULL))\s*$"
)


def evaluate_condition(condition: str, context: dict[str, object]) -> bool:
    """context maps field name -> the request's actual value for that field
    (None if not set). Returns True only if every clause is satisfied."""
    clauses = [c.strip() for c in condition.split(" AND ") if c.strip()]
    if not clauses:
        raise RuleParseError(f"Empty condition: {condition!r}")

    return all(_evaluate_clause(clause, context) for clause in clauses)


def _evaluate_clause(clause: str, context: dict[str, object]) -> bool:
    match = _CLAUSE_RE.match(clause)
    if not match:
        raise RuleParseError(f"Could not parse condition clause: {clause!r}")

    field = match.group("field")
    if field not in KNOWN_FIELDS:
        raise RuleParseError(f"Unknown field in condition: {field!r}")

    actual = context.get(field)

    if match.group("null_op"):
        is_null = match.group("null_op") == "IS NULL"
        return (actual is None) == is_null

    op = match.group("op")
    raw_value = match.group("value").strip().strip('"').strip("'")

    if actual is None:
        # A null actual value never satisfies a comparison operator (only
        # IS NULL/IS NOT NULL can meaningfully test for absence) — this is
        # exactly what makes "amount IS NULL" the correct way to express
        # FLOWFORGE_SPEC.md's "required information is missing" rule, rather
        # than e.g. "amount > 100000" happening to be true for a missing value.
        return False

    if field in NUMERIC_FIELDS:
        try:
            expected = float(raw_value)
            actual_num = float(actual)
        except (TypeError, ValueError) as exc:
            raise RuleParseError(f"Expected a number for {field!r}, got {raw_value!r}") from exc
        return _compare(actual_num, op, expected)

    actual_str = actual.value if hasattr(actual, "value") else str(actual)
    return _compare(actual_str, op, raw_value)


def _compare(actual: float | str, op: str, expected: float | str) -> bool:
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == ">=":
        return actual >= expected
    if op == "<=":
        return actual <= expected
    if op == ">":
        return actual > expected
    if op == "<":
        return actual < expected
    raise RuleParseError(f"Unsupported operator: {op!r}")
