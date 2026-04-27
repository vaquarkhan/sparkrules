from __future__ import annotations

import pytest

from sre.compiler import CompiledRulePackage
from sre.compiler.classifier import Strategy, StrategyClassifier


def test_classifier_sql_join_two_patterns() -> None:
    c = StrategyClassifier()
    src = """
rule r
when
$a : A ( true ) and $b : B ( true )
then
end
"""
    assert c.classify(src) == Strategy.SQL_JOIN


def test_classifier_dataframe_single_pattern_simple_constraint() -> None:
    c = StrategyClassifier()
    src = """
rule r
when
$t : T ( true )
then
result.ok = 1;
end
"""
    assert c.classify(src) == Strategy.DATAFRAME


def test_deserialize_rejects_non_package() -> None:
    import pickle

    b = pickle.dumps({"not": "package"})
    with pytest.raises(TypeError, match="invalid package"):
        CompiledRulePackage.deserialize(b)


def test_serialize_deserialize_roundtrip() -> None:
    from sre.compiler import RuleCompiler

    pkg = RuleCompiler().compile({"a": "rule a when $t : T ( true ) then end"}, run_id="r1")
    pkg2 = CompiledRulePackage.deserialize(pkg.serialize())
    assert pkg2.rule_set_version == pkg.rule_set_version
    assert pkg2.metadata.get("run_id") == "r1"
