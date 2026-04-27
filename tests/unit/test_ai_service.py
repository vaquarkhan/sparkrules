from __future__ import annotations

from dataclasses import replace
import pytest

from sre.ai import AiService, StubAiProvider, redact_payload


def test_redact_payload() -> None:
    p = {"a": 1, "ssn": "123", "nested": {"ssn": "x"}}
    r = redact_payload(p, {"ssn"})
    assert r["a"] == 1
    assert r["ssn"] != "123"
    assert r["nested"]["ssn"] != "x"


def test_ai_suggestion_lifecycle() -> None:
    svc = AiService(StubAiProvider(), pii_fields={"ssn"})
    out = svc.create_rule_suggestions(
        namespace="default",
        payload={"rule_handle": "h", "facts": [{"ssn": "123"}]},
        principal="u1",
    )
    assert len(out) == 1
    s = out[0]
    with pytest.raises(ValueError, match="simulator evidence required"):
        svc.approve(s.id)
    # mark simulator evidence then approve
    cur = svc.store.get(s.id)
    svc.store.upsert(replace(cur, simulator_result={"ok": True}))
    ap = svc.approve(s.id)
    assert ap.status == "APPROVED"
    rj = svc.reject(s.id)
    assert rj.status == "REJECTED"


def test_ai_store_get_missing() -> None:
    svc = AiService(StubAiProvider())
    with pytest.raises(KeyError):
        svc.store.get("missing-id")

