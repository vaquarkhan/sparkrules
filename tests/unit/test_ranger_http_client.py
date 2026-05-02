from __future__ import annotations

import builtins
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

import sparkrules.policy as policy_pkg
from sparkrules.policy.ranger_client import RangerPolicyError, query_ranger_allowed


def test_policy_pkg_exports_ranger_http() -> None:
    assert policy_pkg.query_ranger_allowed is query_ranger_allowed
    assert policy_pkg.RangerPolicyError is RangerPolicyError


def test_query_ranger_allowed_ok() -> None:
    resp = MagicMock(status_code=200, text='{"isAllowed":true}')
    resp.json.return_value = {"isAllowed": True}
    with patch.object(httpx, "post", return_value=resp) as hp:
        assert query_ranger_allowed(
            "http://ranger/",
            user="alice",
            resource_type="dataset",
            resource_name="labs",
            action="read",
        )
    hp.assert_called_once()
    url = hp.call_args.args[0]
    assert url.endswith("/ranger-compat/access-eval")


def test_query_ranger_custom_path_field_and_extra_payload() -> None:
    resp = MagicMock(status_code=200, text="{}")
    resp.json.return_value = {"allowed": False}
    with patch.object(httpx, "post", return_value=resp) as hp:
        out = query_ranger_allowed(
            "http://gw/",
            user="u",
            resource_type="t",
            resource_name="n",
            action="x",
            evaluate_path="/v1/check",
            result_field="allowed",
            extra_payload={"traceId": "abc"},
        )
    assert out is False
    body = hp.call_args.kwargs["json"]
    assert body["traceId"] == "abc" and body["accessType"] == "x"


def test_query_ranger_http_errors() -> None:
    bad = MagicMock(status_code=403, text="no")
    with patch.object(httpx, "post", return_value=bad):
        with pytest.raises(RangerPolicyError, match="403"):
            query_ranger_allowed("http://r/", user="u", resource_type="t", resource_name="n", action="a")

    bad_json = MagicMock(status_code=200, text="[")
    bad_json.json.side_effect = json.JSONDecodeError("x", "[", 0)
    with patch.object(httpx, "post", return_value=bad_json):
        with pytest.raises(RangerPolicyError, match="not JSON"):
            query_ranger_allowed("http://r/", user="u", resource_type="t", resource_name="n", action="a")

    not_obj = MagicMock(status_code=200, text="[]")
    not_obj.json.return_value = []
    with patch.object(httpx, "post", return_value=not_obj):
        with pytest.raises(RangerPolicyError, match="JSON object"):
            query_ranger_allowed("http://r/", user="u", resource_type="t", resource_name="n", action="a")

    missing = MagicMock(status_code=200, text="{}")
    missing.json.return_value = {"other": True}
    with patch.object(httpx, "post", return_value=missing):
        with pytest.raises(RangerPolicyError, match="isAllowed"):
            query_ranger_allowed("http://r/", user="u", resource_type="t", resource_name="n", action="a")

    wrong_type = MagicMock(status_code=200, text="{}")
    wrong_type.json.return_value = {"isAllowed": "yes"}
    with patch.object(httpx, "post", return_value=wrong_type):
        with pytest.raises(RangerPolicyError, match="boolean"):
            query_ranger_allowed("http://r/", user="u", resource_type="t", resource_name="n", action="a")

    with patch.object(httpx, "post", side_effect=OSError("down")):
        with pytest.raises(RangerPolicyError, match="down"):
            query_ranger_allowed("http://r/", user="u", resource_type="t", resource_name="n", action="a")


def test_query_ranger_requires_httpx() -> None:
    real_import = builtins.__import__

    def _block(name: str, /, *args: object, **kwargs: object) -> object:
        if name == "httpx":
            raise ImportError("no")
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", _block):
        with pytest.raises(RuntimeError, match="httpx"):
            query_ranger_allowed("http://r/", user="u", resource_type="t", resource_name="n", action="a")
