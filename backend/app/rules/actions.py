"""Parses workflow_rules.action — a single `key = value` statement.

Supported keys:
    assign_team      = <team name>              (e.g. "IT Security Team")
    status            = <RequestStatus member>    (e.g. "NEEDS_INFORMATION", "MANUAL_REVIEW")
    require_approval  = true
    mark_urgent       = true

One action per rule, matching every example in FLOWFORGE_SPEC.md's rule
engine section — admins wanting multiple effects from the same condition
create multiple rules, which keeps each rule's audit trail entry
("this ONE rule did this ONE thing") easy to read.
"""
import re

from app.rules.exceptions import RuleParseError

_ACTION_RE = re.compile(r"^\s*(?P<key>\w+)\s*=\s*(?P<value>.+?)\s*$")

VALID_KEYS = {"assign_team", "status", "require_approval", "mark_urgent"}


def parse_action(action: str) -> tuple[str, str]:
    match = _ACTION_RE.match(action)
    if not match:
        raise RuleParseError(f"Could not parse action: {action!r}")

    key = match.group("key")
    if key not in VALID_KEYS:
        raise RuleParseError(f"Unknown action key: {key!r} (expected one of {sorted(VALID_KEYS)})")

    value = match.group("value").strip().strip('"').strip("'")
    return key, value
