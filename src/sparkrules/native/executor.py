"""Drop-in scorer backed by Tier-1 Rust kernel (optional wheel)."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from sparkrules.compiler.rulepack import RulePack
from sparkrules.executor.local_executor import RuleFire, ScoreResult

from sparkrules.native.ast_json import rulepack_to_native_json
from sparkrules.native.bridge import NativeUnavailableError, load_native


def score_result_from_native_dict(d: Mapping[str, Any]) -> ScoreResult:
    fires_raw = d["fires"]
    fires: list[RuleFire] = []
    for fr in fires_raw:
        fires.append(
            RuleFire(
                rule_name=fr["rule_name"],
                salience=int(fr["salience"]),
                fired=bool(fr["fired"]),
                action_output=dict(fr["action_output"]),
                reason_codes=tuple(fr["reason_codes"]),
            )
        )
    return ScoreResult(
        fires=fires,
        fired_any=bool(d["fired_any"]),
        merged_actions=dict(d["merged_actions"]),
    )


class NativeRuleExecutor:
    """Rust Tier-1 scalar interpreter (parity contract: ``LocalRuleExecutor.score``).

    Raises :class:`NativeUnavailableError` if ``sparkrules-native`` / ``sparkrules_native`` is absent.
    """

    def __init__(self, compiled: Any, *, pack: RulePack, native: Any) -> None:
        self._compiled = compiled
        self.rulepack = pack
        self._native = native

    @staticmethod
    def from_drl(drl: str) -> NativeRuleExecutor:
        native = load_native()
        if native is None:
            raise NativeUnavailableError(
                "sparkrules_native extension not available; pip install sparkrules-native "
                "and run `maturin develop --release -m sparkrules_native` from the repo "
                "(or keep using LocalRuleExecutor). SPARKRULES_NATIVE_DISABLE=1 skips loading."
            )
        pack = RulePack.from_drl(drl)
        ast_json = rulepack_to_native_json(pack)
        compiled = native.compile_rulepack(ast_json)
        return NativeRuleExecutor(compiled, pack=pack, native=native)

    @staticmethod
    def from_rulepack(pack: RulePack) -> NativeRuleExecutor:
        native = load_native()
        if native is None:
            raise NativeUnavailableError(
                "sparkrules_native extension not available; use LocalRuleExecutor instead."
            )
        ast_json = rulepack_to_native_json(pack)
        compiled = native.compile_rulepack(ast_json)
        return NativeRuleExecutor(compiled, pack=pack, native=native)

    def score(self, fact: Mapping[str, Any]) -> ScoreResult:
        """Score one fact via Rust (``PyDict`` / mapping in, ``dict`` out — no ``json`` on the hot path)."""
        row = self._native.score_rows(self._compiled, [fact])[0]
        return score_result_from_native_dict(row)

    def apply(self, facts: Sequence[Mapping[str, Any]]) -> list[ScoreResult]:
        rows = self._native.score_rows(self._compiled, list(facts))
        return [score_result_from_native_dict(r) for r in rows]
