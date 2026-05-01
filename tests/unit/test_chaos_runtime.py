from __future__ import annotations

from sparkrules.runtime import ChaosPolicy, run_chaos_scenario


def test_chaos_success_first_try() -> None:
    out = run_chaos_scenario(lambda: 7, ChaosPolicy())
    assert out.ok is True
    assert out.value == 7
    assert out.attempts == 1
    assert out.injected_failures == 0


def test_chaos_injected_then_success() -> None:
    out = run_chaos_scenario(
        lambda: {"ok": True},
        ChaosPolicy(fail_on_attempts=(1,), max_retries=2),
    )
    assert out.ok is True
    assert out.attempts == 2
    assert out.injected_failures == 1
    assert "injected_failure:1" in out.events


def test_chaos_exhausted_on_injected_failure() -> None:
    out = run_chaos_scenario(
        lambda: {"ok": True},
        ChaosPolicy(fail_on_attempts=(1,), max_retries=0),
    )
    assert out.ok is False
    assert out.error_class == "InjectedFailure"


def test_chaos_function_exception_path() -> None:
    def _boom() -> object:
        raise ValueError("bad")

    out = run_chaos_scenario(_boom, ChaosPolicy(max_retries=0))
    assert out.ok is False
    assert out.error_class == "ValueError"
    assert out.error_message == "bad"


def test_chaos_timeout_before_attempt() -> None:
    out = run_chaos_scenario(
        lambda: 1,
        ChaosPolicy(timeout_ms=-1),
    )
    assert out.ok is False
    assert out.timed_out is True
    assert out.error_class == "TimeoutError"
