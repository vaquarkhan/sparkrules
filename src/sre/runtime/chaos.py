from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable


@dataclass(frozen=True, slots=True)
class ChaosPolicy:
    fail_on_attempts: tuple[int, ...] = ()
    max_retries: int = 0
    timeout_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ChaosResult:
    ok: bool
    attempts: int
    injected_failures: int
    timed_out: bool
    elapsed_ms: float
    value: Any = None
    error_class: str | None = None
    error_message: str | None = None
    events: tuple[str, ...] = field(default_factory=tuple)


def run_chaos_scenario(fn: Callable[[], Any], policy: ChaosPolicy | None = None) -> ChaosResult:
    pol = policy or ChaosPolicy()
    fail_set = set(pol.fail_on_attempts)
    events: list[str] = []
    injected = 0
    max_attempts = max(1, pol.max_retries + 1)
    t0 = perf_counter()
    for attempt in range(1, max_attempts + 1):
        elapsed = (perf_counter() - t0) * 1000.0
        if pol.timeout_ms is not None and elapsed > pol.timeout_ms:
            events.append(f"timeout_before_attempt:{attempt}")
            return ChaosResult(
                ok=False,
                attempts=attempt - 1,
                injected_failures=injected,
                timed_out=True,
                elapsed_ms=elapsed,
                error_class="TimeoutError",
                error_message="scenario timed out",
                events=tuple(events),
            )
        if attempt in fail_set:
            injected += 1
            events.append(f"injected_failure:{attempt}")
            continue
        try:
            value = fn()
            elapsed = (perf_counter() - t0) * 1000.0
            events.append(f"success:{attempt}")
            return ChaosResult(
                ok=True,
                attempts=attempt,
                injected_failures=injected,
                timed_out=False,
                elapsed_ms=elapsed,
                value=value,
                events=tuple(events),
            )
        except Exception as e:  # noqa: BLE001
            events.append(f"exception:{attempt}:{type(e).__name__}")
            if attempt == max_attempts:
                elapsed = (perf_counter() - t0) * 1000.0
                return ChaosResult(
                    ok=False,
                    attempts=attempt,
                    injected_failures=injected,
                    timed_out=False,
                    elapsed_ms=elapsed,
                    error_class=type(e).__name__,
                    error_message=str(e),
                    events=tuple(events),
                )
    elapsed = (perf_counter() - t0) * 1000.0
    return ChaosResult(
        ok=False,
        attempts=max_attempts,
        injected_failures=injected,
        timed_out=False,
        elapsed_ms=elapsed,
        error_class="InjectedFailure" if injected else "RuntimeError",
        error_message="injected chaos failure" if injected else "unexpected scenario termination",
        events=tuple(events),
    )
