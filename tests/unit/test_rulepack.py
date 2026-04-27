from __future__ import annotations

import json

import pytest

from sre.api.rulepack import FORMAT_ID, build_export_payload, parse_import_body, unified_diff_drl


def test_unified_diff_identical() -> None:
    assert unified_diff_drl("a", "a") == ""


def test_unified_diff_different() -> None:
    d = unified_diff_drl("a\nb", "a\nc")
    assert "version_a" in d and "version_b" in d
    assert "b" in d or "c" in d


def test_build_and_parse_roundtrip() -> None:
    rules = [
        {"rule_handle": "h1", "version": 1, "rule_group": "g", "drl": "rule x when $t: T (true) then end"},
    ]
    s = build_export_payload(rules)
    d = json.loads(s)
    assert d["format"] == FORMAT_ID
    back = parse_import_body(s)
    assert len(back) == 1
    assert back[0]["rule_handle"] == "h1"
    assert back[0]["group"] == "g"
    assert "T (true)" in back[0]["drl"]


def test_parse_import_uses_items_key() -> None:
    body = json.dumps(
        {
            "format": FORMAT_ID,
            "items": [
                {
                    "rule_handle": "a",
                    "group": "x",
                    "drl": "rule r when $t: T (true) then end",
                }
            ],
        }
    )
    p = parse_import_body(body)
    assert p[0]["rule_handle"] == "a"
    assert p[0]["group"] == "x"


def test_parse_import_errors() -> None:
    with pytest.raises(ValueError, match="object"):
        parse_import_body("[]")
    with pytest.raises(ValueError, match="unsupported format"):
        parse_import_body(json.dumps({"format": "other", "rules": []}))
    with pytest.raises(ValueError, match="items or rules"):
        parse_import_body(json.dumps({}))
    with pytest.raises(ValueError, match="item 0"):
        parse_import_body(json.dumps({"rules": [1, 2]}))
    with pytest.raises(ValueError, match="rule_handle and drl"):
        parse_import_body(
            json.dumps(
                {
                    "format": FORMAT_ID,
                    "rules": [{"rule_handle": "a"}],
                }
            )
        )
