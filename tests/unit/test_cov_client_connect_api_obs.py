from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from sre.api import AppDeps, create_app
from sre.client import SreClient, SreClientError, install_transient_failure
from sre.connect import ConnectServer
from sre.obs import metrics
from sre.obs.logging import bind_run_context, configure_logging, get_logger
from sre.store import InMemoryRuleMetadataStore
from sre.model.rule import Rule, RuleDefinition, RuleFormat, new_rule_id
from datetime import UTC, datetime, timedelta


def test_sre_client_get_success() -> None:
    c = SreClient("http://example.com")
    mock_resp = httpx.Response(200, json={"status": "ok", "a": 1})
    m = MagicMock()
    m.__enter__ = MagicMock(
        return_value=MagicMock(get=MagicMock(return_value=mock_resp))
    )
    m.__exit__ = MagicMock(return_value=False)
    with patch("sre.client.sdk.httpx.Client", return_value=m):
        r = c.get("/health")
    assert r.status_code == 200


def test_sre_client_exhausts_injected_failures() -> None:
    c = SreClient("http://example.com", _tries=3)
    install_transient_failure(c, 3)
    with pytest.raises(SreClientError, match="injected|unreachable"):
        c.get("/z")


def test_sre_client_retry_injected() -> None:
    c = SreClient("http://example.com", _tries=2)
    install_transient_failure(c, 1)
    g = 0
    r200 = httpx.Response(200, json={"k": 1})
    m = MagicMock()
    inner = MagicMock()

    def gget(*_a, **_k):
        nonlocal g
        g += 1
        return r200

    inner.get = gget
    m.__enter__ = MagicMock(return_value=inner)
    m.__exit__ = MagicMock(return_value=False)
    with patch("sre.client.sdk.httpx.Client", return_value=m):
        c.get("/x")
    assert g == 1


def test_sre_client_health() -> None:
    c = SreClient("http://example.com")
    m = MagicMock()
    r = httpx.Response(200, json={"status": "ok"}, request=httpx.Request("GET", "http://example.com/health"))
    m.__enter__ = MagicMock(return_value=MagicMock(get=MagicMock(return_value=r)))
    m.__exit__ = MagicMock(return_value=False)
    with patch("sre.client.sdk.httpx.Client", return_value=m):
        j = c.health()
    assert j["status"] == "ok"


def test_sre_client_post_validate_and_simulate() -> None:
    c = SreClient("http://example.com")
    reqs: list[tuple[str, object]] = []
    m = MagicMock()
    inner = MagicMock()

    def ppost(url: str, *, json, timeout: float):  # noqa: ANN001
        reqs.append((url, json))
        if url.endswith("/rules/validate"):
            return httpx.Response(
                200,
                json={"ok": True},
                request=httpx.Request("POST", url),
            )
        return httpx.Response(
            200,
            json={"fired": True, "action": {"ok": True}},
            request=httpx.Request("POST", url),
        )

    inner.post = ppost
    m.__enter__ = MagicMock(return_value=inner)
    m.__exit__ = MagicMock(return_value=False)
    with patch("sre.client.sdk.httpx.Client", return_value=m):
        v = c.validate_rule("rule r when $t : T ( true ) then end")
        s = c.simulate("rule r when $t : T ( true ) then end", {"t": {}})
    assert v["ok"] is True
    assert s["fired"] is True
    assert len(reqs) == 2


def test_sre_client_post_direct_and_bad_method_path() -> None:
    c = SreClient("http://example.com")
    m = MagicMock()
    inner = MagicMock()
    inner.post = MagicMock(
        return_value=httpx.Response(
            200,
            json={"ok": True},
            request=httpx.Request("POST", "http://example.com/x"),
        )
    )
    m.__enter__ = MagicMock(return_value=inner)
    m.__exit__ = MagicMock(return_value=False)
    with patch("sre.client.sdk.httpx.Client", return_value=m):
        assert c.post("/x", {"a": 1}).status_code == 200
    with pytest.raises(SreClientError, match="unsupported method"):
        c._request("PUT", "/x")


def test_sre_client_advanced_simulation_methods() -> None:
    c = SreClient("http://example.com")
    m = MagicMock()
    inner = MagicMock()

    def ppost(url: str, *, json, timeout: float):  # noqa: ANN001
        if url.endswith("/simulations/counterfactual"):
            return httpx.Response(200, json={"drifted": True}, request=httpx.Request("POST", url))
        if url.endswith("/debug/time-travel/capture"):
            return httpx.Response(200, json={"snapshot_id": 1}, request=httpx.Request("POST", url))
        if url.endswith("/debug/time-travel/replay"):
            return httpx.Response(200, json={"fired": True}, request=httpx.Request("POST", url))
        return httpx.Response(200, json={"enforced_rules": 1}, request=httpx.Request("POST", url))

    inner.post = ppost
    m.__enter__ = MagicMock(return_value=inner)
    m.__exit__ = MagicMock(return_value=False)
    with patch("sre.client.sdk.httpx.Client", return_value=m):
        assert c.counterfactual("rule r when $t : T ( true ) then end", {"t": {}}, {"t": {}})["drifted"] is True
        assert c.capture_time_travel("r1", "rule r when $t : T ( true ) then end", {"t": {}})["snapshot_id"] == 1
        assert c.replay_time_travel(1, "r1", {"t": {"x": 2}})["fired"] is True
        assert c.enforce_deprecations("default", "h1")["enforced_rules"] == 1


def test_connect_list_and_parse_and_keyerror() -> None:
    s = InMemoryRuleMetadataStore()
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    s.insert(
        Rule(
            new_rule_id(),
            "a1",
            0,
            "g",
            0,
            t0,
            None,
            True,
            RuleDefinition("x", RuleFormat.DRL),
            None,
        )
    )
    cv = ConnectServer(store=s)
    assert cv.dispatch("list_rules") == ["a1"]
    assert cv.dispatch("parse", "rule p when $t : T(1==1) then end") == "p"
    with pytest.raises(KeyError):
        cv.dispatch("missing", "x")


def test_obs_configure_console_and_logger() -> None:
    buf = io.StringIO()
    configure_logging(json_only=False)
    lg = get_logger("t1")
    assert lg is not None
    b = bind_run_context("r99")
    assert b is not None


def test_metrics_app_has_route() -> None:
    a = metrics.metrics_endpoint_app()
    c = TestClient(a)
    r = c.get("/metrics")
    assert r.status_code == 200
    assert "HELP" in r.text or len(r.text) > 0


def test_post_rule_422_on_bad_drl() -> None:
    app = create_app(AppDeps())
    c = TestClient(app)
    r = c.post(
        "/rules",
        json={"rule_handle": "h", "group": "g", "drl": "not a rule at all {{"},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "DRL_PARSE_ERROR"


def test_sre_init_module() -> None:
    import sre

    assert hasattr(sre, "__version__")
