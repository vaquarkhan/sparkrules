from __future__ import annotations

from unittest.mock import patch

import pytest

from sparkrules.policy.ranger_compat import ranger_allow_stub


def test_ranger_allow_stub_local_mode_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPARKRULES_RANGER_BASE_URL", raising=False)
    assert ranger_allow_stub(user="", resource_type="t", resource_name="n", action="a") is False
    assert ranger_allow_stub(user="u", resource_type="t", resource_name="n", action="a") is True


def test_ranger_allow_stub_delegates_when_base_url_set() -> None:
    env = {
        "SPARKRULES_RANGER_BASE_URL": "http://policy.local",
        "SPARKRULES_RANGER_EVAL_PATH": "/eval",
        "SPARKRULES_RANGER_RESULT_FIELD": "isAllowed",
    }
    with patch.dict("os.environ", env, clear=False):
        with patch(
            "sparkrules.policy.ranger_compat.query_ranger_allowed",
            return_value=True,
        ) as m:
            ok = ranger_allow_stub(
                user="alice", resource_type="tbl", resource_name="t", action="read"
            )
    assert ok is True
    m.assert_called_once()
    call_kw = m.call_args.kwargs
    assert call_kw["evaluate_path"] == "/eval"
    assert call_kw["result_field"] == "isAllowed"


def test_ranger_allow_stub_fail_closed_on_policy_error() -> None:
    from sparkrules.policy.ranger_client import RangerPolicyError

    env = {"SPARKRULES_RANGER_BASE_URL": "http://policy.local"}
    with patch.dict("os.environ", env, clear=False):
        with patch(
            "sparkrules.policy.ranger_compat.query_ranger_allowed",
            side_effect=RangerPolicyError("down"),
        ):
            assert (
                ranger_allow_stub(user="u", resource_type="t", resource_name="n", action="a")
                is False
            )


def test_ranger_eval_path_normalized() -> None:
    env = {
        "SPARKRULES_RANGER_BASE_URL": "http://policy.local",
        "SPARKRULES_RANGER_EVAL_PATH": "no-leading-slash",
    }
    with patch.dict("os.environ", env, clear=False):
        with patch(
            "sparkrules.policy.ranger_compat.query_ranger_allowed",
            return_value=True,
        ) as m:
            ranger_allow_stub(user="u", resource_type="t", resource_name="n", action="a")
    assert m.call_args.kwargs["evaluate_path"] == "/no-leading-slash"
