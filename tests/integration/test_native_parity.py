"""Parity checks: Tier-1 ``sparkrules_native`` vs ``LocalRuleExecutor`` (skipped without wheel).

Set ``SPARKRULES_NATIVE_PARITY_EXAMPLES`` (default 20; raise locally toward 500+).
"""

from __future__ import annotations

import os

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sparkrules.executor.local_executor import LocalRuleExecutor
from sparkrules.native.bridge import NativeUnavailableError, load_native

pytestmark = pytest.mark.integration

_SIMPLE = """
rule r0 when $t : T ( $t.amount > 5 ) then result.flag = true; end
rule r1 when $t : T ( $t.amount <= 5 ) then result.flag = false; end
"""

_elem = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=-10_000, max_value=10_000)
    | st.text(max_size=8),
    lambda ch: ch.map(lambda x: {"v": x}) | st.lists(ch, max_size=4),
    max_leaves=6,
)


@st.composite
def shaped_fact(draw):
    inner = draw(
        st.dictionaries(
            st.sampled_from(["amount", "x", "flag", "s"]),
            _elem,
            max_size=5,
        ),
    )
    return {"t": inner}


_examples = max(1, int(os.environ.get("SPARKRULES_NATIVE_PARITY_EXAMPLES", "20")))


@given(fact=shaped_fact())
@settings(max_examples=_examples, deadline=None)
def test_native_equals_local_hypothesis(fact: dict) -> None:
    if load_native() is None:
        pytest.skip("sparkrules_native not installed")
    from sparkrules.native.executor import NativeRuleExecutor

    loc = LocalRuleExecutor.from_drl(_SIMPLE).score(fact)
    native = NativeRuleExecutor.from_drl(_SIMPLE).score(fact)
    assert loc.fires == native.fires
    assert loc.fired_any == native.fired_any
    assert loc.merged_actions == native.merged_actions


def test_native_fixed_vectors_simple_pack() -> None:
    """Deterministic parity smoke (skipped without native)."""
    if load_native() is None:
        pytest.skip("sparkrules_native not installed")
    from sparkrules.native.executor import NativeRuleExecutor

    drl = 'rule chk when $t : T ( $t.n contains "ab" ) then result.z = len($t.n); end'
    facts = [
        {"t": {"n": "zabc"}},
        {"t": {"n": ["a", "b"]}},
        {"t": {"n": {"ab": 1}}},
        {"t": {}},
    ]
    loc_ex = LocalRuleExecutor.from_drl(drl)
    nat_ex = NativeRuleExecutor.from_drl(drl)
    for fct in facts:
        l_ = loc_ex.score(fct)
        n_ = nat_ex.score(fct)
        assert l_.fires == n_.fires
        assert l_.fired_any == n_.fired_any
        assert l_.merged_actions == n_.merged_actions


def test_native_executor_missing_wheel_message() -> None:
    if load_native() is not None:
        pytest.skip("sparkrules_native is installed")
    from sparkrules.native.executor import NativeRuleExecutor

    with pytest.raises(NativeUnavailableError):
        NativeRuleExecutor.from_drl(_SIMPLE)
