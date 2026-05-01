from __future__ import annotations

import pytest

from sparkrules.governance import PromotionRegistry


def test_set_get_pin() -> None:
    r = PromotionRegistry()
    r.set_pin("n1", "h", "dev", 2)
    assert r.get_pin("n1", "h", "dev") == 2
    assert r.get_pin("n1", "h", "stage") is None


def test_promote_adjacent() -> None:
    r = PromotionRegistry()
    r.set_pin("n1", "h", "dev", 3)
    v = r.promote("n1", "h", "dev", "stage")
    assert v == 3
    assert r.get_pin("n1", "h", "stage") == 3


def test_promote_to_prod() -> None:
    r = PromotionRegistry()
    r.set_pin("n1", "h", "stage", 1)
    assert r.promote("n1", "h", "stage", "prod") == 1


def test_promote_rejects_non_adjacent() -> None:
    r = PromotionRegistry()
    r.set_pin("n1", "h", "dev", 1)
    with pytest.raises(ValueError, match="only adjacent"):
        r.promote("n1", "h", "dev", "prod")


def test_promote_rejects_empty_source() -> None:
    r = PromotionRegistry()
    with pytest.raises(ValueError, match="source environment"):
        r.promote("n1", "h", "dev", "stage")


def test_set_pin_unknown_env() -> None:
    r = PromotionRegistry()
    with pytest.raises(ValueError, match="unknown environment"):
        r.set_pin("n", "h", "qa", 1)


def test_all_pins_filter() -> None:
    r = PromotionRegistry()
    r.set_pin("a", "h1", "dev", 1)
    r.set_pin("b", "h2", "dev", 2)
    assert len(r.all_pins("a")) == 1
    assert len(r.all_pins(None)) == 2
