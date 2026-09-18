class RuleParseError(Exception):
    """A rule's condition or action text couldn't be parsed. Raised for
    admin-entered rules that don't match the supported grammar — the engine
    catches this per-rule and skips just that rule rather than failing the
    whole evaluation (see app/rules/engine.py)."""
