"""Cover remaining lines for full sre line coverage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from sparkrules.compiler.evaluator import _eval, _get_id, _set_result_path
from sparkrules.compiler.evaluator import evaluate_expr
from sparkrules.executor import RuleExecutor
from sparkrules.ioxls.importer import _coerce
from sparkrules.model import ColumnType
from sparkrules.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from sparkrules.parser import parse, print_ast
from sparkrules.parser import ast as past
from sparkrules.parser.lexer import TokenKind, tokenize
from sparkrules.parser.ast import (
    Action,
    BinaryOp,
    BinaryOperator,
    CallExpr,
    FactPattern,
    FieldAccess,
    Identifier,
    Literal,
    ParseError,
    RuleAst,
)
from sparkrules.parser.lexer import Token
from sparkrules.parser.parser import DrlParser, _bind_root, _collect_idents, _unquote
from sparkrules.runtime.batch import RunRecord
from sparkrules.runtime.cache import DerivedColumnCache
from sparkrules.runtime.catalyst import CatalystConfigurer
from sparkrules.runtime.iceberg_store import IcebergLikeTable
from sparkrules.runtime.streaming import (
    StreamingEvaluator,
    StreamingRuleRefresher,
    default_executor_factory,
)
from sparkrules.sim.ab import ABTestConfig, ABTestRunner, Variant
from sparkrules.sim.replay import MissingRuleSetVersionError, ReplayService
from sparkrules.store import InMemoryRuleMetadataStore, RuleFilter
from sparkrules.transport.broadcaster import RuleBroadcaster


def test_get_id_branches() -> None:
    assert _get_id("result", {"result": {"x": 1}}) == {"x": 1}
    assert _get_id("result.a.b", {"result": {"a": {"b": 9}}}) == 9
    assert _get_id("$t.x", {"t": None}) is None
    assert _get_id("$t.x", {"t": {}}) is None


def test_set_result_path_non_dict() -> None:
    env: dict = {"result": []}
    _set_result_path("result.x", 9, env)
    assert env["result"] == {"x": 9}


def test_field_access_and_le_ge_gt_abs_string() -> None:
    assert _eval(FieldAccess("t", "f"), {"t": 9}) is None
    assert _eval(BinaryOp(BinaryOperator.LE, Literal(1), Literal(3)), {}) is True
    assert _eval(BinaryOp(BinaryOperator.GE, Literal(4), Literal(2)), {}) is True
    assert _eval(CallExpr("abs", (Literal("z"),)), {}) == "z"


def test_eval_unknown_expr() -> None:
    class _X:
        pass

    with pytest.raises(TypeError):
        _eval(_X(), {})


def test_eval_expr_le_ge() -> None:
    assert evaluate_expr(BinaryOp(BinaryOperator.LE, Literal(2), Literal(2)), {}) is True
    assert evaluate_expr(BinaryOp(BinaryOperator.GE, Literal(1), Literal(0)), {}) is True


def test_executor_not_fired_preserves_reason_codes() -> None:
    ex = RuleExecutor()
    drl = """rule q
    reason_codes [ "RC1" ]
    when $t : T ( false )
    then result.x = 1;
    end"""
    fr = ex.run({"t": {}}, drl)
    assert fr.fired is False and fr.reason_codes == ("RC1",)


def test_executor_join_sql_and_error_and_not_fired() -> None:
    ex = RuleExecutor()
    j = ex.run(
        {"id": "1"},
        "rule j when $a : A ( true ) and $b : B ( true ) then end",
    )
    assert j.error_class == "SqlJoinNotImplemented"
    err = ex.run(
        {"t": {}},
        "rule e when $t : T ( badf(1) ) then end",
    )
    assert err.error_class == "ValueError"
    nf = ex.run(
        {"x": 0},
        "rule f when $t : T ( $t.x > 0 ) then end",
    )
    assert nf.fired is False
    fj = ex.run(
        {"a": [{"x": 0}, {"x": 1}], "b": [{"y": 2}]},
        "rule j2 when $a : A ( $a.x > 0 ) and $b : B ( true ) then result.ok = true; end",
        allow_sql_join=True,
    )
    assert fj.fired is True
    nj = ex.run(
        {"a": [{"x": 0}], "b": [{"y": 2}]},
        "rule j3 when $a : A ( $a.x > 9 ) and $b : B ( true ) then result.ok = true; end",
        allow_sql_join=True,
    )
    assert nj.fired is False


def test_coerce_string_empty_bool_strings_fallback() -> None:
    assert _coerce("", ColumnType.STRING, 1, 1) == ""
    assert _coerce(True, ColumnType.BOOL, 1, 1) is True
    assert _coerce("1", ColumnType.BOOL, 1, 1) is True
    assert _coerce("0", ColumnType.BOOL, 1, 1) is False
    assert _coerce(99, object(), 1, 1) == 99  # type: ignore[arg-type]


def test_parser_helpers_collect_fieldaccess() -> None:
    assert _unquote("x") == "x"
    assert _unquote("noquote") == "noquote"
    assert _bind_root("p.q") == "p"
    _collect_idents(FieldAccess("a", "b"))


def test_ident_base_property() -> None:
    assert Identifier("only").base == "only"
    assert Identifier("first.second").base == "first"


def test_parse_empty_when_constraint() -> None:
    r = parse("rule e when $t : T() then result.x = 1; end")
    assert r.when[0].constraint is None


def test_parse_false_null_float_literals() -> None:
    s = "rule z when $t : T ( true ) then result.x = false; result.y = null; result.z = 2.5; end"
    r = parse(s)
    o = print_ast(r)
    assert "false" in o and "null" in o


def test_parse_expect_failure_and_bad_action() -> None:
    with pytest.raises(Exception):  # ParseError
        parse("rule b when $t : T ( true ) then oops = 1; end")
    p = DrlParser()
    p._toks = [Token(TokenKind.EOF, "", 1, 1)]
    p._i = 0
    with pytest.raises(Exception):
        p._expect(TokenKind.RULE)


def test_ident_suffix_non_identifier_passthrough() -> None:
    p = DrlParser()
    lit = Literal(9)
    assert p._ident_suffix(lit) is lit  # type: ignore[arg-type]


def test_parse_primary_unexpected_token() -> None:
    p = DrlParser()
    p._toks = [
        Token(TokenKind.COMMA, ",", 1, 1),
        Token(TokenKind.EOF, "", 1, 1),
    ]
    p._i = 0
    with pytest.raises(ParseError, match="Unexpected"):
        p._parse_primary()


def test_parse_fn_args_and_bad_primary() -> None:
    parse("rule c when $t : T ( $t.x in [1, 2] ) then result.a = f(1, 2); end")
    with pytest.raises(ValueError, match="Unexpected"):
        tokenize("?")
    p = DrlParser()
    p._toks = [
        Token(TokenKind.ASSIGN, "=", 1, 1),
        Token(TokenKind.EOF, "", 1, 1),
    ]
    p._i = 0
    with pytest.raises(ParseError):
        p._parse_primary()


def test_lexer_single_quoted_string() -> None:
    t = tokenize("rule a when $t : T ( 'x' ) then end")
    assert any(x.kind == TokenKind.STRING for x in t)
    t2 = tokenize("'a\nsecond'")
    assert "\n" in next(x.text for x in t2 if x.kind == TokenKind.STRING)


def test_lexer_comment_le_ge_unclosed() -> None:
    toks = tokenize("// c\nrule x when $t : T ( $t.a <= 1 and $t.b >= 2 ) then end")
    assert TokenKind.LE in [x.kind for x in toks]
    assert TokenKind.GE in [x.kind for x in toks]
    with pytest.raises(ValueError, match="unclosed"):
        tokenize('r when $t : T ( "nope )')
    with pytest.raises(ValueError):
        tokenize("r when $t : T ( 'nope )")


def test_lexer_multiline_double_quoted_string() -> None:
    tokenize('"a\nsecond"')


def test_print_ast_empty_constraint_pattern() -> None:
    r = RuleAst(
        "p",
        0,
        "MAIN",
        None,
        None,
        (),
        (),
        False,
        (FactPattern("b", "F", None),),
        (Action("result.x", Literal(1)),),
    )
    o = print_ast(r)
    assert "F ( )" in o.replace("  ", " ")


def test_printer_fieldaccess_fallback_and_drl_printer() -> None:
    r = RuleAst(
        "z",
        0,
        "MAIN",
        None,
        None,
        (),
        (),
        False,
        (FactPattern("t", "T", FieldAccess("x", "y")),),
        (),
    )
    out = print_ast(r)
    assert "y" in out or "FieldAccess" in out
    from sparkrules.parser.printer import DrlPrinter, _print_expr

    assert "3" in _print_expr(Literal(3))
    assert '"' in _print_expr(Literal('a"b'))
    assert _print_expr(Literal(False)) == "false"
    assert _print_expr(Literal(None)) == "null"
    assert "not" in _print_expr(past.Not(Literal(True)))
    assert "[" in _print_expr(past.ListExpr((Literal(1), Literal(2))))
    assert "not in" in _print_expr(
        past.InExpr(
            Literal(1),
            past.ListExpr((Literal(2),)),
            negated=True,
        )
    )
    assert "(" in _print_expr(past.CallExpr("g", (Literal(1),)))
    p = DrlPrinter()
    assert p.print(parse("rule q when $t : T ( true ) then end"))


def test_runtime_and_sim() -> None:
    c = DerivedColumnCache()
    assert c.get((0, "k")) is None
    c.put((0, "k"), 1)
    assert c.get((0, "k")) == 1
    assert c.size() == 1
    c.clear()
    assert c.size() == 0

    t = IcebergLikeTable("N", {"x": int})
    t.append([{"x": 1}])
    assert t.row_count(t.current_snapshot_id()) == 1

    assert default_executor_factory() == "in_process"

    ab = ABTestRunner()
    assert ab.assign("u", ABTestConfig("k", (Variant("A", 0), Variant("Z", 0)))) == "Z"
    assert ab.assign("k2", ABTestConfig("f", (Variant("A", 1), Variant("B", 1)))) in (
        "A",
        "B",
    )


def test_list_active_filter_skips_inactive() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2018, 1, 1, tzinfo=UTC)
    s.insert(
        Rule(
            new_rule_id(),
            "za",
            0,
            "g",
            0,
            t0,
            None,
            False,
            RuleDefinition("x", RuleFormat.DRL),
            None,
        )
    )
    s.insert(
        Rule(
            new_rule_id(),
            "zb",
            0,
            "g",
            0,
            t0,
            None,
            True,
            RuleDefinition("x", RuleFormat.DRL),
            None,
        )
    )
    act = s.list(RuleFilter(is_active=True))
    assert len(act) == 1 and act[0].rule_handle == "zb"


def test_chunk_empty_multi_and_metadata_inactive_list() -> None:
    assert RuleBroadcaster(256).chunk(b"")[0].payload == b""
    ch = RuleBroadcaster(3).chunk(b"abcdef")
    assert len(ch) > 1

    s = InMemoryRuleMetadataStore()
    t0 = datetime(2030, 1, 1, tzinfo=UTC)
    s.insert(
        Rule(
            new_rule_id(),
            "hid",
            0,
            "g1",
            0,
            t0,
            None,
            False,
            RuleDefinition("x", RuleFormat.DRL),
            None,
        )
    )
    lst = s.list(RuleFilter(rule_handle="hid", is_active=False))
    assert len(lst) == 1 and lst[0].is_active is False


def test_catalyst_configurer() -> None:
    c = CatalystConfigurer()
    assert c.rules.get("fusion_enabled") is True


def test_streaming_refresher_same_version_and_recompile_ok() -> None:
    r = StreamingRuleRefresher("v0")
    assert r.maybe_refresh("v0", recompile=None) is None

    def rec() -> object:
        return object()

    assert r.maybe_refresh("v1", recompile=rec) == "v1"
    assert r.current == "v1"


def test_streaming_recompile_fails() -> None:
    r = StreamingRuleRefresher("v0")

    def bad() -> object:
        raise RuntimeError("no")

    assert r.maybe_refresh("v1", recompile=bad) is None
    assert r.current == "v0"


def test_streaming_evaluator_ttl() -> None:
    e = StreamingEvaluator(timedelta(seconds=1))
    t0 = datetime(2021, 1, 1, 12, 0, 0, tzinfo=UTC)
    assert e.check_ttl(t0, None) is True
    assert e.check_ttl(t0, t0) is False
    assert e.check_ttl(t0 + timedelta(seconds=2), t0) is True


def test_replay_mismatch() -> None:
    t0 = datetime(2019, 1, 1, tzinfo=UTC)
    rr = RunRecord(
        run_id="r1",
        mode="b",
        input_table_name="T",
        input_snapshot_id=0,
        rule_set_version="a",
        config_fingerprint="c",
        start_ts=t0,
        end_ts=t0,
        facts_processed=0,
        rules_fired=0,
        rules_errored=0,
        status="x",
        error_class=None,
        error_message=None,
    )
    with pytest.raises(MissingRuleSetVersionError):
        ReplayService().replay(rr, "other")


def test_replay_match() -> None:
    t0 = datetime(2019, 1, 1, tzinfo=UTC)
    rr = RunRecord(
        run_id="run-x",
        mode="b",
        input_table_name="T",
        input_snapshot_id=0,
        rule_set_version="v9",
        config_fingerprint="c",
        start_ts=t0,
        end_ts=t0,
        facts_processed=0,
        rules_fired=0,
        rules_errored=0,
        status="x",
        error_class=None,
        error_message=None,
    )
    assert ReplayService().replay(rr, "v9") == "run-x"


def test_parse_rule_reason_codes_list_with_comma() -> None:
    s = DrlParser().parse('rule r reason_codes [ "a", "b" ] when $t : T ( true ) then end')
    assert s.reason_codes == ("a", "b")
