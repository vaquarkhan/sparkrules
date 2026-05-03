"""RulePack deserialization hardening — restricted GLOBAL targets (SECURITY)."""

from __future__ import annotations

import pickle
from pickle import UnpicklingError

import pytest

from sparkrules.compiler.exceptions import RulePackVersionError
from sparkrules.compiler.rulepack import (
    RULEPACK_SER_MAJOR_VERSION,
    RULEPACK_SER_MINOR_VERSION,
    RulePack,
)
from sparkrules.compiler.safe_pickle import _restricted_find_class, loads_rulepack_payload
from sparkrules.executor.local_executor import LocalRuleExecutor


def _minimal_rulepack_blob() -> bytes:
    return RulePack.from_drl(
        'rule "r" when $t : T ( $t.a > 0 ) then result.b = true; end',
    ).serialize()


def test_restricted_find_class_rejects_foreign_modules() -> None:
    with pytest.raises(UnpicklingError, match="unsafe module"):
        _restricted_find_class("posix", "system")


def test_restricted_find_class_rejects_missing_sparkrules_attr() -> None:
    with pytest.raises(UnpicklingError, match="missing RulePack pickle global"):
        _restricted_find_class("sparkrules.compiler.rulepack", "__NoSuchPickleGlobal__")


def test_restricted_pickle_rejects_non_sparkrules_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reject GLOBAL targets outside ``sparkrules.*`` (except ``builtins.getattr`` for Enum glue)."""

    monkeypatch.delenv("SPARKRULES_RULEPACK_UNSAFE_PICKLE", raising=False)
    with pytest.raises(UnpicklingError):
        loads_rulepack_payload(pickle.dumps(len, protocol=4))


def test_restricted_pickle_rejects_foreign_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPARKRULES_RULEPACK_UNSAFE_PICKLE", raising=False)
    with pytest.raises(UnpicklingError):
        loads_rulepack_payload(pickle.dumps(print, protocol=4))


def test_unsafe_pickles_env_restores_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_RULEPACK_UNSAFE_PICKLE", "1")
    blob = pickle.dumps({"recover": True}, protocol=4)
    assert loads_rulepack_payload(blob)["recover"]


def test_rulepack_roundtrip_via_deserialize_accepted() -> None:
    obj = RulePack.deserialize(_minimal_rulepack_blob())
    assert isinstance(obj, RulePack)
    assert len(obj.rules) == 1


def test_rulepack_deserialize_wraps_pickle_attack_on_object() -> None:
    raw = pickle.dumps(object(), protocol=4)
    with pytest.raises(RulePackVersionError, match=r"(?i)(malformed|unsafe|rejected)"):
        RulePack.deserialize(raw)


def test_local_executor_pickles_via_rulepack_bytes() -> None:
    ex = LocalRuleExecutor.from_drl('rule "r" when $t:T($t.a>5)then result.x=42; end')
    raw = pickle.dumps(ex)
    ex2 = pickle.loads(raw)
    assert isinstance(ex2, LocalRuleExecutor)
    assert ex2.rulepack.drl_hash == ex.rulepack.drl_hash
    assert ex2.score({"t": {"a": 10}}).merged_actions["x"] == 42


def test_srrp_envelope_preserves_hashes() -> None:
    rp = RulePack.from_drl("rule qq when $t:T(true)then end")
    envelope = (
        b"SRRP"
        + bytes([RULEPACK_SER_MAJOR_VERSION, RULEPACK_SER_MINOR_VERSION])
        + pickle.dumps(rp, protocol=4)
    )
    restored = RulePack.deserialize(envelope)
    assert restored.drl_hash == rp.drl_hash
