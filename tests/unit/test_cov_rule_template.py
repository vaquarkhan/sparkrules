from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sparkrules.model.rule_template import (
    ExtraPlaceholderError,
    MissingPlaceholderError,
    RuleTemplate,
    _substitute,
    ast_from_template,
)
from sparkrules.parser.ast import RuleAst


def test_substitute_missing() -> None:
    t = RuleTemplate.from_pattern("n", "hello {a} {b}")
    with pytest.raises(MissingPlaceholderError):
        _substitute(t.pattern, {"a": "1"}, t.placeholders)


def test_substitute_extra() -> None:
    t = RuleTemplate.from_pattern("n", "hello {a}")
    with pytest.raises(ExtraPlaceholderError):
        _substitute(t.pattern, {"a": "1", "z": "2"}, t.placeholders)


def test_ast_from_template_extra_in_values() -> None:
    t = RuleTemplate.from_pattern("n", "rule r1 when $t : T ( true ) then end")
    with pytest.raises(ExtraPlaceholderError):
        ast_from_template(t, {"bad": "x"})


def test_ast_from_template_missing_placeholder() -> None:
    t = RuleTemplate.from_pattern("n", "rule {name} when $t : T ( true ) then end")
    with pytest.raises(MissingPlaceholderError):
        ast_from_template(t, {})


def test_ast_from_template_injected_parser() -> None:
    t = RuleTemplate.from_pattern("n", "rule r1 when $t : T ( true ) then end")
    p = MagicMock()
    p.parse = MagicMock(return_value=MagicMock(spec=RuleAst))
    ast_from_template(t, {}, _parser=p)
    p.parse.assert_called_once()


def test_ast_from_template_default_drl_parser() -> None:
    t = RuleTemplate.from_pattern("n", "rule {name} when $t : T ( true ) then end")
    a = ast_from_template(t, {"name": "x9"})
    assert a.name == "x9"
