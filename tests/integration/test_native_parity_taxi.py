"""Parity: 30-rule taxi synthetic pack vs ``LocalRuleExecutor`` (skipped without native).

Uses ``sparkrules_native/tests/fixtures/taxi_rules_30.drl``. Set
``SPARKRULES_NATIVE_PARITY_EXAMPLES`` (default matches ``test_native_parity``).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from sparkrules.executor.local_executor import LocalRuleExecutor
from sparkrules.native.bridge import load_native

pytestmark = pytest.mark.integration

_REPO = Path(__file__).resolve().parents[2]
_TAXI_DRL = (_REPO / "sparkrules_native" / "tests" / "fixtures" / "taxi_rules_30.drl").read_text(
    encoding="utf-8",
)

_ELEM = st.recursive(
    st.none()
    | st.booleans()
    | st.integers(min_value=-10_000, max_value=10_000)
    | st.floats(allow_nan=False, allow_infinity=False, min_value=-500.0, max_value=500.0),
    lambda ch: ch.map(lambda x: {"v": x}) | st.lists(ch, max_size=8),
    max_leaves=8,
)

_TRIP_KEYS = frozenset(
    {
        "fare",
        "distance",
        "pax",
        "tip_pct",
        "city",
        "code",
        "bad_driver",
        "surged",
        "delta",
        "notes",
        "fare_int",
        "vip",
        "pickup_hour",
        "dropoff_hour",
        "echo_fare",
        "rating",
    },
)


@st.composite
def taxi_shaped_fact(draw):
    inner = draw(
        st.dictionaries(
            st.sampled_from(sorted(_TRIP_KEYS)),
            _ELEM,
            max_size=len(_TRIP_KEYS),
        ),
    )
    return {"t": inner}


_examples = max(1, int(os.environ.get("SPARKRULES_NATIVE_PARITY_EXAMPLES", "20")))


@given(fact=taxi_shaped_fact())
@settings(max_examples=_examples, deadline=None)
def test_native_taxi_pack_equals_local_hypothesis(fact: dict) -> None:
    if load_native() is None:
        pytest.skip("sparkrules_native not installed")
    from sparkrules.native.executor import NativeRuleExecutor

    loc = LocalRuleExecutor.from_drl(_TAXI_DRL).score(fact)
    native = NativeRuleExecutor.from_drl(_TAXI_DRL).score(fact)
    assert loc.fires == native.fires
    assert loc.fired_any == native.fired_any
    assert loc.merged_actions == native.merged_actions


def test_native_taxi_fixed_smoke_vectors() -> None:
    """Hand-picked vectors covering contains, ``in``, ``matches``, graveyard hour."""
    if load_native() is None:
        pytest.skip("sparkrules_native not installed")
    from sparkrules.native.executor import NativeRuleExecutor

    loc_ex = LocalRuleExecutor.from_drl(_TAXI_DRL)
    nat_ex = NativeRuleExecutor.from_drl(_TAXI_DRL)
    vectors = [
        {
            "t": {
                "fare": 12.5,
                "distance": 0.5,
                "pax": 1,
                "tip_pct": 8,
                "city": "Brooklyn, NY",
                "code": "L1",
                "bad_driver": False,
                "surged": True,
                "delta": -2,
                "notes": ["a", "b", "c", "d", "e"],
                "fare_int": 12,
                "vip": False,
                "pickup_hour": 23,
                "dropoff_hour": 1,
                "echo_fare": 12.5,
                "rating": 4.8,
            }
        },
        {
            "t": {
                "fare": -1,
                "distance": 10,
                "pax": 4,
                "tip_pct": 30,
                "city": "LA downtown",
                "code": "X",
                "bad_driver": True,
                "surged": False,
                "delta": 100,
                "notes": "",
                "fare_int": None,
                "vip": True,
                "pickup_hour": 2,
                "dropoff_hour": 14,
                "echo_fare": 99,
                "rating": 3.2,
            }
        },
    ]
    for fct in vectors:
        l_ = loc_ex.score(fct)
        n_ = nat_ex.score(fct)
        assert l_.fires == n_.fires
        assert l_.fired_any == n_.fired_any
        assert l_.merged_actions == n_.merged_actions
