from __future__ import annotations

import difflib
import json
from datetime import UTC, datetime
from typing import Any

FORMAT_ID = "sparkrules-rulepack-1"


def unified_diff_drl(drl_a: str, drl_b: str) -> str:
    a = drl_a.splitlines(keepends=True)
    b = drl_b.splitlines(keepends=True)
    return "".join(
        difflib.unified_diff(a, b, fromfile="version_a", tofile="version_b", lineterm="")
    )


def build_export_payload(rules: list[dict[str, Any]]) -> str:
    body = {
        "format": FORMAT_ID,
        "exported_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "items": rules,
    }
    return json.dumps(body, indent=2, sort_keys=True)


def parse_import_body(raw: str) -> list[dict[str, Any]]:
    d = json.loads(raw)
    if not isinstance(d, dict):
        raise ValueError("body must be a JSON object")
    fmt = d.get("format")
    if fmt is not None and fmt != FORMAT_ID:
        raise ValueError(f"unsupported format: {fmt!r}")
    items = d.get("items") if "items" in d else d.get("rules")
    if not isinstance(items, list):
        raise ValueError("import requires items or rules array")
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            raise ValueError(f"item {i} must be an object")
        h = it.get("rule_handle")
        drl = it.get("drl")
        if not h or not drl:
            raise ValueError(f"item {i} needs rule_handle and drl")
        g = it.get("group", it.get("rule_group", "default"))
        ns = it.get("namespace", "default")
        out.append(
            {
                "rule_handle": str(h),
                "group": str(g),
                "namespace": str(ns),
                "drl": str(drl),
            }
        )
    return out
