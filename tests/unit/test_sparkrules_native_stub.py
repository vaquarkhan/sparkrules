"""Optional ``sparkrules_native`` extension (wheel) vs Python ``sparkrules.native`` API."""

from __future__ import annotations

from types import ModuleType
from unittest.mock import patch

import pytest

from sparkrules.native.bridge import load_native


def test_sparkrules_native_disable_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_NATIVE_DISABLE", "1")
    assert load_native() is None


def test_sparkrules_python_native_module_exists() -> None:
    """Public surface for optional acceleration (bridge + executor)."""

    import sparkrules.native

    assert sparkrules.native.load_native is load_native


def test_load_native_returns_module_when_abi_complete() -> None:
    good = ModuleType("sparkrules_native")
    good.compile_rulepack = lambda _s: None
    good.score_rows = lambda *_a: []
    good.native_version = lambda: "0.1.0"
    good.rulepack_hash = lambda _s: "x"
    with patch.dict("sys.modules", {"sparkrules_native": good}, clear=False):
        from sparkrules.native.bridge import load_native

        assert load_native() is good


def test_load_native_rejects_partial_extension_module() -> None:
    bad = ModuleType("sparkrules_native")
    bad.native_version = lambda: "0"

    def _compile(_s: object) -> object:
        return None

    bad.compile_rulepack = _compile
    bad.score_rows = lambda *_a: []

    with patch.dict("sys.modules", {"sparkrules_native": bad}, clear=False):
        assert load_native() is None
