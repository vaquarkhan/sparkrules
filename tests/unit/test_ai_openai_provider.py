from __future__ import annotations

import io
import json
from unittest.mock import MagicMock, patch

import pytest

from sparkrules.ai.openai_provider import (
    OpenAiHttpAiProvider,
    _normalize_dq_items,
    _normalize_rule_rows,
    openai_provider_from_env,
)
from sparkrules.ai.service import create_default_ai_provider, StubAiProvider


def test_normalize_rule_rows_list_and_dict() -> None:
    rows = [{"rule_handle": "a", "drl": "rule a when $t : T ( true ) then end"}]
    assert _normalize_rule_rows(rows) == rows
    assert _normalize_rule_rows({"rules": rows}) == rows
    assert _normalize_rule_rows({"other": 1}) == []


def test_normalize_dq_items() -> None:
    items = [{"kind": "not_null", "field": "id", "severity": "WARN"}]
    assert _normalize_dq_items({"items": items}) == items
    assert _normalize_dq_items(items) == items
    assert _normalize_dq_items({"items": "x"}) == []


def _patch_urlopen_chat_response(content_obj: object) -> object:
    api_body = {
        "choices": [{"message": {"content": json.dumps(content_obj)}}],
    }
    inner_read = MagicMock()
    inner_read.read.return_value = json.dumps(api_body).encode()
    cm = MagicMock()
    cm.__enter__.return_value = inner_read
    cm.__exit__.return_value = False
    return patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm)


def test_chat_completion_json_success_suggest_rules() -> None:
    inner = {"rules": [{"rule_handle": "gen1", "drl": "rule gen1 when $t : T ( true ) then end"}]}
    p = OpenAiHttpAiProvider(api_key="k", base_url="https://api.example/v1", model="m")
    with _patch_urlopen_chat_response(inner):
        out = p.suggest_rules({"facts": [], "rule_handle": "base"})
    assert out[0]["rule_handle"] == "gen1" and "gen1" in out[0]["drl"]


def test_suggest_rules_raises_when_model_returns_empty_rules() -> None:
    p = OpenAiHttpAiProvider(api_key="k")
    with _patch_urlopen_chat_response({"rules": []}):
        with pytest.raises(RuntimeError, match="no usable rule"):
            p.suggest_rules({})


def test_openai_http_error_surfaces() -> None:
    import urllib.error

    p = OpenAiHttpAiProvider(api_key="k")

    def boom(*_a: object, **_k: object):
        raise urllib.error.HTTPError(
            "url",
            401,
            "Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"err":1}'),
        )

    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", side_effect=boom):
        with pytest.raises(RuntimeError, match="OpenAI HTTP 401"):
            p.suggest_rules({})


def test_chat_completion_invalid_inner_json() -> None:
    inner_read = MagicMock()
    inner_read.read.return_value = json.dumps(
        {"choices": [{"message": {"content": "not-json"}}]},
    ).encode()
    cm = MagicMock()
    cm.__enter__.return_value = inner_read
    cm.__exit__.return_value = False
    p = OpenAiHttpAiProvider(api_key="k")
    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm):
        with pytest.raises(RuntimeError, match="not valid JSON"):
            p.suggest_rules({})


def test_openai_provider_from_env_requires_key() -> None:
    with patch.dict("os.environ", {"SPARKRULES_OPENAI_API_KEY": ""}, clear=False):
        assert openai_provider_from_env() is None
    with patch.dict("os.environ", {"SPARKRULES_OPENAI_API_KEY": "secret"}, clear=False):
        p = openai_provider_from_env()
        assert p is not None and p.api_key == "secret"


def test_create_default_ai_provider_modes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPARKRULES_AI_PROVIDER", raising=False)
    monkeypatch.delenv("SPARKRULES_OPENAI_API_KEY", raising=False)
    assert isinstance(create_default_ai_provider(), StubAiProvider)
    monkeypatch.setenv("SPARKRULES_AI_PROVIDER", "openai")
    monkeypatch.delenv("SPARKRULES_OPENAI_API_KEY", raising=False)
    assert isinstance(create_default_ai_provider(), StubAiProvider)
    monkeypatch.setenv("SPARKRULES_OPENAI_API_KEY", "x")
    p = create_default_ai_provider()
    assert getattr(p, "provider_name", "") == "openai"


def test_mine_dq_rules_openai() -> None:
    inner = {"items": [{"kind": "not_null", "field": "x", "severity": "ERROR"}]}
    p = OpenAiHttpAiProvider(api_key="k")
    with _patch_urlopen_chat_response(inner):
        out = p.mine_dq_rules({"field": "x"})
    assert out[0]["kind"] == "not_null"


def test_analyze_drift_openai() -> None:
    inner = {"status": "warn", "drift_score": 0.5, "note": "n"}
    p = OpenAiHttpAiProvider(api_key="k")
    with _patch_urlopen_chat_response(inner):
        out = p.analyze_drift({"a": 1})
    assert out["status"] == "warn" and out["drift_score"] == 0.5


def test_chat_completion_json_url_error() -> None:
    import urllib.error

    p = OpenAiHttpAiProvider(api_key="k")
    with patch(
        "sparkrules.ai.openai_provider.urllib.request.urlopen",
        side_effect=urllib.error.URLError("no route"),
    ):
        with pytest.raises(RuntimeError, match="OpenAI request failed"):
            p.suggest_rules({})


def test_chat_completion_json_bad_outer_shape() -> None:
    inner_read = MagicMock()
    inner_read.read.return_value = b"[]"
    cm = MagicMock()
    cm.__enter__.return_value = inner_read
    cm.__exit__.return_value = False
    p = OpenAiHttpAiProvider(api_key="k")
    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm):
        with pytest.raises(RuntimeError, match="JSON object"):
            p.suggest_rules({})


def test_chat_completion_json_envelope_not_json() -> None:
    inner_read = MagicMock()
    inner_read.read.return_value = b"not-json"
    cm = MagicMock()
    cm.__enter__.return_value = inner_read
    cm.__exit__.return_value = False
    p = OpenAiHttpAiProvider(api_key="k")
    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm):
        with pytest.raises(RuntimeError, match="envelope not JSON"):
            p.suggest_rules({})


def test_chat_completion_json_missing_choices() -> None:
    inner_read = MagicMock()
    inner_read.read.return_value = json.dumps({"choices": []}).encode()
    cm = MagicMock()
    cm.__enter__.return_value = inner_read
    cm.__exit__.return_value = False
    p = OpenAiHttpAiProvider(api_key="k")
    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm):
        with pytest.raises(RuntimeError, match="missing choices"):
            p.suggest_rules({})


def test_chat_completion_json_bad_message_shape() -> None:
    inner_read = MagicMock()
    inner_read.read.return_value = json.dumps({"choices": [{"message": "x"}]}).encode()
    cm = MagicMock()
    cm.__enter__.return_value = inner_read
    cm.__exit__.return_value = False
    p = OpenAiHttpAiProvider(api_key="k")
    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm):
        with pytest.raises(RuntimeError, match="missing message"):
            p.suggest_rules({})


def test_chat_completion_json_empty_message_content() -> None:
    inner_read = MagicMock()
    inner_read.read.return_value = json.dumps(
        {"choices": [{"message": {"content": "   "}}]},
    ).encode()
    cm = MagicMock()
    cm.__enter__.return_value = inner_read
    cm.__exit__.return_value = False
    p = OpenAiHttpAiProvider(api_key="k")
    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm):
        with pytest.raises(RuntimeError, match="content empty"):
            p.suggest_rules({})

    inner_read2 = MagicMock()
    inner_read2.read.return_value = json.dumps(
        {"choices": [{"message": {"content": 1}}]},
    ).encode()
    cm2 = MagicMock()
    cm2.__enter__.return_value = inner_read2
    cm2.__exit__.return_value = False
    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm2):
        with pytest.raises(RuntimeError, match="content empty"):
            p.suggest_rules({})


def test_chat_completion_text_http_and_shape_errors() -> None:
    import urllib.error

    p = OpenAiHttpAiProvider(api_key="k")

    def mk_read(data: bytes):
        inner_read = MagicMock()
        inner_read.read.return_value = data
        cm = MagicMock()
        cm.__enter__.return_value = inner_read
        cm.__exit__.return_value = False
        return cm

    with patch(
        "sparkrules.ai.openai_provider.urllib.request.urlopen",
        side_effect=urllib.error.HTTPError(
            "u",
            500,
            "err",
            hdrs=None,
            fp=io.BytesIO(b"x"),
        ),
    ):
        with pytest.raises(RuntimeError, match="OpenAI HTTP 500"):
            p.explain_rule({"drl": "x"})

    with patch(
        "sparkrules.ai.openai_provider.urllib.request.urlopen",
        side_effect=urllib.error.URLError("x"),
    ):
        with pytest.raises(RuntimeError, match="OpenAI request failed"):
            p.explain_rule({"drl": "x"})

    with patch(
        "sparkrules.ai.openai_provider.urllib.request.urlopen",
        return_value=mk_read(b"[]"),
    ):
        with pytest.raises(RuntimeError, match="JSON object"):
            p.explain_rule({"drl": "x"})

    with patch(
        "sparkrules.ai.openai_provider.urllib.request.urlopen",
        return_value=mk_read(b"not-json"),
    ):
        with pytest.raises(RuntimeError, match="envelope not JSON"):
            p.explain_rule({"drl": "x"})

    with patch(
        "sparkrules.ai.openai_provider.urllib.request.urlopen",
        return_value=mk_read(json.dumps({"choices": []}).encode()),
    ):
        with pytest.raises(RuntimeError, match="missing choices"):
            p.explain_rule({"drl": "x"})

    with patch(
        "sparkrules.ai.openai_provider.urllib.request.urlopen",
        return_value=mk_read(json.dumps({"choices": [{"message": 1}]}).encode()),
    ):
        with pytest.raises(RuntimeError, match="missing message"):
            p.explain_rule({"drl": "x"})


def test_normalize_rule_rows_skips_non_dict_and_alt_keys() -> None:
    mixed = [1, {"rule_handle": "a", "drl": "rule a when $t : T ( true ) then end"}]
    assert len(_normalize_rule_rows(mixed)) == 1
    alt = {"suggestions": [{"rule_handle": "b", "drl": "rule b when $t : T ( true ) then end"}]}
    assert _normalize_rule_rows(alt)[0]["rule_handle"] == "b"
    cand = {"candidates": [{"rule_handle": "c", "drl": "rule c when $t : T ( true ) then end"}]}
    assert _normalize_rule_rows(cand)[0]["rule_handle"] == "c"
    bad_cells = [{"rule_handle": 1, "drl": "x"}, {"rule_handle": "d", "drl": ""}]
    assert _normalize_rule_rows(bad_cells) == []


def test_normalize_dq_items_non_list_branch() -> None:
    assert _normalize_dq_items({"items": {}}) == []
    assert _normalize_dq_items(123) == []


def test_normalize_rule_rows_dict_without_list_values() -> None:
    assert _normalize_rule_rows({"rules": 1, "suggestions": None}) == []


def test_normalize_rule_rows_non_collection() -> None:
    assert _normalize_rule_rows(None) == []


def test_mine_dq_rules_raises_when_empty_items() -> None:
    p = OpenAiHttpAiProvider(api_key="k")
    with _patch_urlopen_chat_response({"items": []}):
        with pytest.raises(RuntimeError, match="no DQ items"):
            p.mine_dq_rules({})


def test_openai_provider_from_env_custom_base(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPARKRULES_OPENAI_API_KEY", "k")
    monkeypatch.setenv("SPARKRULES_OPENAI_BASE_URL", "https://gateway.example/v1")
    monkeypatch.setenv("SPARKRULES_OPENAI_MODEL", "gpt-test")
    p = openai_provider_from_env()
    assert p is not None
    assert p.base_url == "https://gateway.example/v1" and p.model == "gpt-test"


def test_explain_rule_openai_text() -> None:
    api_body = {"choices": [{"message": {"content": "Short explanation."}}]}
    inner_read = MagicMock()
    inner_read.read.return_value = json.dumps(api_body).encode()
    cm = MagicMock()
    cm.__enter__.return_value = inner_read
    cm.__exit__.return_value = False
    p = OpenAiHttpAiProvider(api_key="k")
    with patch("sparkrules.ai.openai_provider.urllib.request.urlopen", return_value=cm):
        assert (
            p.explain_rule({"drl": "rule r when $t : T ( true ) then end"}) == "Short explanation."
        )
