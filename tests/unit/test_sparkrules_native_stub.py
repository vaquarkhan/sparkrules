from __future__ import annotations


def test_sparkrules_native_stub_importable() -> None:
    import sparkrules_native

    assert "native" in (sparkrules_native.__doc__ or "").lower()
