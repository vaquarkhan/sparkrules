"""Meta: ``sparkrules_native`` Rust and Python publishing versions stay aligned."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "relative",
    [
        "sparkrules_native/Cargo.toml",
        "sparkrules_native/pyproject.toml",
    ],
)
def test_native_manifests_exist(relative: str) -> None:
    assert (_REPO / relative).is_file()


def test_native_wheel_version_matches_cargo() -> None:
    cargo_toml = tomllib.loads(
        (_REPO / "sparkrules_native" / "Cargo.toml").read_text(encoding="utf-8"),
    )
    py_toml = tomllib.loads(
        (_REPO / "sparkrules_native" / "pyproject.toml").read_text(encoding="utf-8"),
    )

    assert cargo_toml["package"]["version"] == py_toml["project"]["version"]
