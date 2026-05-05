"""Regression: setuptools must package all ``sparkrules.*`` subpackages (incl. ``native``)."""

from __future__ import annotations

from pathlib import Path

from setuptools import find_packages

_REPO = Path(__file__).resolve().parents[2]


def test_find_packages_includes_native_subpackage() -> None:
    src = _REPO / "src"
    wide = sorted(find_packages(where=str(src), include=["sparkrules*"]))
    narrow = sorted(find_packages(where=str(src), include=["sparkrules"]))

    assert "sparkrules.native" in wide, "sparkrules.native must ship in wheel/sdist for [native]"
    assert "sparkrules" in wide
    assert narrow == ["sparkrules"], (
        "sanity: bare 'sparkrules' include must not list subpackages (regression premise)"
    )
