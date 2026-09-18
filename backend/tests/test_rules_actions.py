import pytest

from app.rules.actions import parse_action
from app.rules.exceptions import RuleParseError


def test_parses_assign_team() -> None:
    assert parse_action("assign_team = IT Security Team") == ("assign_team", "IT Security Team")


def test_parses_status() -> None:
    assert parse_action("status = MANUAL_REVIEW") == ("status", "MANUAL_REVIEW")


def test_parses_quoted_value() -> None:
    assert parse_action('assign_team = "IT Security Team"') == ("assign_team", "IT Security Team")


def test_unknown_key_raises() -> None:
    with pytest.raises(RuleParseError):
        parse_action("delete_everything = true")


def test_unparseable_action_raises() -> None:
    with pytest.raises(RuleParseError):
        parse_action("not an action at all")
