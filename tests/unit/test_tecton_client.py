from __future__ import annotations

import builtins
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import sparkrules.integrations as integrations_pkg
from sparkrules.integrations.tecton_client import (
    TectonFeatureClient,
    tecton_fetch_row,
)
from sparkrules.integrations.feast_client import merge_features_into_fact


def test_integration_package_exports_tecton() -> None:
    assert integrations_pkg.TectonFeatureClient is not None
    assert callable(integrations_pkg.tecton_fetch_row)
    assert integrations_pkg.merge_features_into_fact is merge_features_into_fact


def test_tecton_fetch_row_when_client_none() -> None:
    assert tecton_fetch_row(None, join_key_field="uid", join_value="1") == {}


def test_tecton_fetch_row_delegates_with_context() -> None:
    inner = MagicMock()
    inner.get_features.return_value.get_features_dict.return_value = {"risk": 0.1}
    cli = TectonFeatureClient(_client=inner, feature_service_name="fraud:v1")
    out = tecton_fetch_row(
        cli,
        feature_service_name=None,
        join_key_field="customer_id",
        join_value="c-9",
        request_context_map={"amount_usd": 199.0},
    )
    assert out == {"risk": 0.1}
    kw = inner.get_features.call_args.kwargs
    assert kw["join_key_map"] == {"customer_id": "c-9"}
    assert kw["request_context_map"] == {"amount_usd": 199.0}


def test_get_inference_passes_request_context_and_overrides_service_name() -> None:
    inner = MagicMock()
    inner.get_features.return_value.get_features_dict.return_value = {}
    cli = TectonFeatureClient(_client=inner, feature_service_name="default:v1")
    cli.get_inference_features(
        feature_service_name="override:v9",
        join_key_map={"a": "b"},
        request_context_map={"amount": 10.5},
    )
    kw = inner.get_features.call_args.kwargs
    assert kw["feature_service_name"] == "override:v9"
    assert kw["request_context_map"] == {"amount": 10.5}


def test_get_inference_via_injected_client_dict_response() -> None:
    cli_inner = MagicMock()
    faux = MagicMock()
    faux.get_features_dict.return_value = {"avg_spend": 12.5}
    cli_inner.get_features.return_value = faux

    cli = TectonFeatureClient(_client=cli_inner, feature_service_name="svc:v2")
    out = cli.get_inference_features(join_key_map={"user_id": "a"})
    assert out["avg_spend"] == 12.5
    cli_inner.get_features.assert_called_once()
    kw = cli_inner.get_features.call_args.kwargs
    assert kw["feature_service_name"] == "svc:v2"
    assert kw["join_key_map"] == {"user_id": "a"}
    assert kw["request_context_map"] == {}


def test_get_inference_fallback_ignores_non_dict_features() -> None:
    cli_inner = MagicMock()
    cli_inner.get_features.return_value = types.SimpleNamespace(
        result=types.SimpleNamespace(features=["not", "a", "dict"]),
    )
    cli = TectonFeatureClient(_client=cli_inner)
    assert cli.get_inference_features(feature_service_name="fs") == {}


def test_get_inference_fallback_result_features() -> None:
    cli_inner = MagicMock()
    resp = types.SimpleNamespace(result=types.SimpleNamespace(features={"f": True}))
    cli_inner.get_features.return_value = resp

    cli = TectonFeatureClient(_client=cli_inner)
    out = cli.get_inference_features(feature_service_name="fs:1")
    assert out == {"f": True}


def test_get_inference_fallback_empty_when_no_payload() -> None:
    cli_inner = MagicMock()
    cli_inner.get_features.return_value = object()
    cli = TectonFeatureClient(_client=cli_inner)
    assert cli.get_inference_features(feature_service_name="x") == {}


def test_get_inference_get_features_dict_none() -> None:
    cli_inner = MagicMock()
    faux = MagicMock()
    faux.get_features_dict.return_value = None
    cli_inner.get_features.return_value = faux
    cli = TectonFeatureClient(_client=cli_inner)
    assert cli.get_inference_features(feature_service_name="y") == {}


def test_missing_feature_service_name_raises() -> None:
    cli = TectonFeatureClient(_client=MagicMock())
    with pytest.raises(ValueError, match="feature_service_name"):
        cli.get_inference_features()


def test_resolve_requires_url_without_injection() -> None:
    cli = TectonFeatureClient(url=None, api_key=None)
    with pytest.raises(ValueError, match="url"):
        cli.get_inference_features(feature_service_name="z")


def test_resolve_import_error_message() -> None:
    cli = TectonFeatureClient(url="https://fake.tecton.ai/", api_key="k")

    real_import = builtins.__import__

    def _block(name: str, /, *args: object, **kwargs: object) -> object:
        if name == "tecton_client":
            raise ImportError("no")
        return real_import(name, *args, **kwargs)

    with patch.object(builtins, "__import__", _block):
        with pytest.raises(RuntimeError, match="tecton-client"):
            cli.get_inference_features(feature_service_name="fs", join_key_map={"id": "1"})


def test_resolve_builds_http_client_without_optional_workspace_kwarg() -> None:
    captured: dict[str, Any] = {}

    def fake_tecton_client(**kwargs: object) -> MagicMock:
        captured.clear()
        captured.update(kwargs)
        inst = MagicMock()
        resp = MagicMock()
        resp.get_features_dict.return_value = {}
        inst.get_features.return_value = resp
        return inst

    mod = types.ModuleType("tecton_client")
    mod.TectonClient = MagicMock(side_effect=fake_tecton_client)
    with patch.dict("sys.modules", {"tecton_client": mod}):
        cli = TectonFeatureClient(url="https://x/", api_key="k")
        cli.get_inference_features(feature_service_name="s")
        assert "default_workspace_name" not in captured


def test_resolve_builds_http_client_with_workspace() -> None:
    captured: dict[str, Any] = {}

    def fake_tecton_client(**kwargs: object) -> MagicMock:
        captured.update(kwargs)
        inst = MagicMock()
        resp = MagicMock()
        resp.get_features_dict.return_value = {"ok": 1}
        inst.get_features.return_value = resp
        return inst

    mod = types.ModuleType("tecton_client")
    mod.TectonClient = MagicMock(side_effect=fake_tecton_client)

    with patch.dict("sys.modules", {"tecton_client": mod}):
        cli = TectonFeatureClient(
            url="https://demo.tecton.ai/",
            api_key="sekret",
            default_workspace_name="prod",
        )
        out = cli.get_inference_features(feature_service_name="fraud_svc:v3", join_key_map={"u": "1"})
        assert out == {"ok": 1}
        assert captured["url"] == "https://demo.tecton.ai/"
        assert captured["api_key"] == "sekret"
        assert captured["default_workspace_name"] == "prod"


def test_merge_alias_from_feast_fact() -> None:
    fact: dict[str, object] = {}
    merge_features_into_fact(fact, {"x-val": 2})
    assert fact["feat_x_val"] == 2
