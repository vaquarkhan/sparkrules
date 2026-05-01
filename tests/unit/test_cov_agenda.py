from __future__ import annotations

import pytest

from sparkrules.executor.agenda import (
    AgendaController,
    ChainingLimitExceededError,
    forward_chain,
    order_activations,
    resolve_activation_groups,
)


def test_forward_chain_stops_on_empty_and_caps_depth() -> None:
    assert forward_chain("a", {"a": []}) == ["a"]
    with pytest.raises(ChainingLimitExceededError):
        forward_chain("a", {"a": ["b"], "b": ["a"]}, max_depth=2)


def test_resolve_activation_groups_skips_dup_group() -> None:
    o = resolve_activation_groups(
        [("a", "G"), ("b", "G"), ("c", None)]
    )
    assert o == ["a", "c"]


def test_order_activations_and_controller() -> None:
    a = order_activations(
        [
            (5, "t", "g", "id1"),
            (10, "t", "g", "id2"),
        ]
    )
    assert a[0] == "id2"
    c = AgendaController()
    a2 = c.order_activations(
        [
            (1, "t", "g", "x"),
        ]
    )
    assert a2 == ["x"]
