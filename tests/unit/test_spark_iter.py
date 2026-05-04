"""Pure-Python tests for sparkrules.spark (no JVM)."""

import json

import pytest

from sparkrules.spark import iter_rule_rows

_DRL = """
rule r1
when
$z : T ( $z.n == 1 )
then
result.x = 1;
end
"""


def test_iter_rule_rows_dict_rows() -> None:
    t = list(
        iter_rule_rows(
            iter(
                [
                    {"id": "1", "z": {"n": 1}},
                    {"id": "2", "z": {"n": 0}},
                ],
            ),
            _DRL,
        )
    )
    assert t[0][0] == "1" and t[0][1] is True
    assert t[1][1] is False


def test_iter_rule_rows_row_with_asdict() -> None:
    """Spark Row-like objects expose asDict() — same path as PySpark DataFrame rows."""

    class RowLike:
        def asDict(self) -> dict:
            return {"id": "9", "z": {"n": 1}}

    t = list(iter_rule_rows(iter([RowLike()]), _DRL))
    assert len(t) == 1 and t[0][0] == "9" and t[0][1] is True


_DRL_NESTED_NUM = """
rule r when $a : A ( $a.fico_score >= 720 ) then result.ok = true; end
"""


def test_iter_rule_rows_prefers_asdict_recursive_true() -> None:
    """PySpark Row.asDict(recursive=True) unwraps nested Row structs to plain dicts."""

    seen: list[bool] = []

    class RowLikeRecursive:
        def asDict(self, recursive: bool = False) -> dict:
            seen.append(bool(recursive))
            if recursive:
                return {"id": "1", "a": {"fico_score": 750}}
            return {"id": "1", "a": {"fico_score": 750}}

    t = list(iter_rule_rows(iter([RowLikeRecursive()]), _DRL_NESTED_NUM))
    assert seen == [True]
    assert t[0][1] is True


def test_iter_rule_rows_asdict_typeerror_fallback_still_evaluates() -> None:
    """Mocks that only implement asDict() without recursive= still work."""

    class RowLegacy:
        def asDict(self) -> dict:
            return {"id": "2", "a": {"fico_score": 800}}

    t = list(iter_rule_rows(iter([RowLegacy()]), _DRL_NESTED_NUM))
    assert t[0][1] is True


def test_iter_rule_rows_empty_drl_raises() -> None:
    with pytest.raises(ValueError, match="at least one"):
        list(iter_rule_rows(iter([{"id": "1", "z": {"n": 1}}]), ""))


_DRL_MULTI = """
rule r1
when $a : T ( $a.x > 0 ) then
    result.p = 1;
end
rule r2
when $a : T ( true ) then
    result.q = 2;
end
"""


def test_iter_rule_rows_multi_rule_chain_path() -> None:
    """Multi-rule DRL uses parse_rules + run_rule_chain (covers dataframe.py chain branch)."""
    t = list(
        iter_rule_rows(
            iter([{"id": "c1", "a": {"x": 1}}]),
            _DRL_MULTI,
            fact_id_field="id",
        )
    )
    assert len(t) == 1
    assert t[0][0] == "c1"
    assert t[0][1] is True
    out = json.loads(t[0][2])
    assert out["action"].get("p") == 1 or out["action"].get("q") == 2


def test_iter_rule_rows_sequence_row_dict_fallback() -> None:
    """Non-dict row without asDict: dict(row) path for Spark Row-like iterables."""
    row = [("id", "seq1"), ("z", {"n": 1})]
    t = list(iter_rule_rows(iter([row]), _DRL))
    assert t[0][0] == "seq1" and t[0][1] is True


def test_iter_rule_rows_v1_sequence_row_dict_fallback() -> None:
    row = [("id", "v1seq"), ("z", {"n": 1})]
    t = list(iter_rule_rows(iter([row]), _DRL, use_v2=False))
    assert t[0][0] == "v1seq" and t[0][1] is True


def test_iter_rule_rows_v1_row_asdict_typeerror_fallback() -> None:
    class RowLegacy:
        def asDict(self, recursive: bool = False) -> dict:
            if recursive:
                raise TypeError("no recursive")
            return {"id": "v1r", "z": {"n": 1}}

    t = list(iter_rule_rows(iter([RowLegacy()]), _DRL, use_v2=False))
    assert t[0][0] == "v1r" and t[0][1] is True


def test_iter_rule_rows_v2_action_exception_sets_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sparkrules.compiler import closure as closure_mod

    real_ca = closure_mod.compile_action

    def wrapping_ca(action: object) -> tuple[str, object]:
        fname, fn = real_ca(action)
        if fname == "x":

            def _boom(_fact: object) -> int:
                raise RuntimeError("simulated action failure")

            return fname, _boom
        return fname, fn

    monkeypatch.setattr(closure_mod, "compile_action", wrapping_ca)
    drl = "rule r when $t : T ( true ) then result.x = 1; end"
    rows = [{"id": "1", "t": {}}]
    results = list(iter_rule_rows(iter(rows), drl, use_v2=True))
    out = json.loads(results[0][2])
    assert out["action"]["x"] is None
