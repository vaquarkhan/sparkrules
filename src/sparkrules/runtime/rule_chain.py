from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, MutableMapping, Sequence

from sparkrules.compiler import evaluate_rule
from sparkrules.compiler.beta_join import refine_eligibility_with_beta_join
from sparkrules.parser.ast import RuleAst

if TYPE_CHECKING:
    from sparkrules.compiler.discrimination import DiscriminationNetwork


@dataclass(frozen=True, slots=True)
class ChainExecutionPolicy:
    """Per-run options for multi-rule (Phase 2k) execution."""

    stop_on_decline: bool = False
    agenda_group_modes: dict[str, str] = field(default_factory=dict)
    max_fires: int | None = None


@dataclass(frozen=True, slots=True)
class ChainStep:
    rule_name: str
    fired: bool
    skipped: bool
    skip_reason: str | None
    action_output: dict[str, Any]
    stop_on_fire: bool = False


@dataclass
class RuleChainResult:
    steps: list[ChainStep] = field(default_factory=list)
    last_fired: bool = False
    final_action: dict[str, Any] = field(default_factory=dict)
    final_bound: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None


def _declined(action: dict[str, Any]) -> bool:
    d = action.get("decision")
    return isinstance(d, str) and d.lower() == "decline"


def _normalize_mode(raw: str | None) -> str:
    v = (raw or "all_matches").strip().lower()
    if v not in {"all_matches", "first_match", "first_failure"}:
        raise ValueError("agenda group mode must be one of all_matches, first_match, first_failure")
    return v


def run_rule_chain(
    rules: Sequence[RuleAst],
    fact: MutableMapping[str, Any],
    policy: ChainExecutionPolicy | None = None,
    discrimination: DiscriminationNetwork | None = None,
) -> RuleChainResult:
    """Run rules in salience order; enforce activation groups, stop_on_fire, stop_on_decline."""
    pol = policy or ChainExecutionPolicy()
    out = RuleChainResult()
    if not rules:
        return out

    ordered = sorted(rules, key=lambda r: (-r.salience, r.name))
    work: dict[str, Any] = {k: v for k, v in fact.items()}
    if discrimination is None:
        eligible = None
    else:
        base = discrimination.eligible_rule_names(work)
        eligible = refine_eligibility_with_beta_join(base, ordered, work)
    consumed_activations: set[str] = set()
    halted_agenda_groups: set[str] = set()
    evaluated = 0

    for r in ordered:
        gname = r.agenda_group
        gmode = _normalize_mode(pol.agenda_group_modes.get(gname))
        if gname in halted_agenda_groups:
            out.steps.append(
                ChainStep(
                    r.name,
                    False,
                    True,
                    f"agenda_group:{gmode}",
                    dict(work.get("result") or {}) if isinstance(work.get("result"), dict) else {},
                )
            )
            continue
        if r.activation_group and r.activation_group in consumed_activations:
            out.steps.append(
                ChainStep(
                    r.name,
                    False,
                    True,
                    "activation_group",
                    dict(work.get("result") or {}) if isinstance(work.get("result"), dict) else {},
                )
            )
            continue
        if eligible is not None and r.name not in eligible:
            out.steps.append(
                ChainStep(
                    r.name,
                    False,
                    True,
                    "discrimination_alpha",
                    dict(work.get("result") or {}) if isinstance(work.get("result"), dict) else {},
                )
            )
            continue
        m = evaluate_rule(r, work, carry_result=(evaluated > 0))
        evaluated += 1
        sk: str | None = None
        work["result"] = dict(m.action_output)
        for k, v in m.bound.items():
            work[k] = v
        if m.fired and r.activation_group:
            consumed_activations.add(r.activation_group)
        step = ChainStep(
            r.name,
            m.fired,
            False,
            sk,
            dict(m.action_output),
            stop_on_fire=bool(m.fired and r.stop_on_fire),
        )
        out.steps.append(step)
        if m.fired:
            out.last_fired = True
        out.final_action = dict(work.get("result") or {})
        if isinstance(m.bound, dict):
            out.final_bound = {k: v for k, v in m.bound.items()}
        if m.fired and gmode == "first_match":
            halted_agenda_groups.add(gname)
        if (not m.fired) and gmode == "first_failure":
            halted_agenda_groups.add(gname)

        if m.fired and r.stop_on_fire:
            out.stop_reason = f"stop_on_fire:{r.name}"
            out.final_bound = {k: v for k, v in work.items() if k != "result"}
            return out
        if m.fired and pol.stop_on_decline and _declined(dict(m.action_output)):
            out.stop_reason = "stop_on_decline"
            out.final_bound = {k: v for k, v in work.items() if k != "result"}
            return out
        if pol.max_fires is not None and pol.max_fires > 0:
            n_fired = sum(1 for s in out.steps if s.fired)
            if n_fired >= pol.max_fires:
                out.stop_reason = "fire_max"
                out.final_bound = {k: v for k, v in work.items() if k != "result"}
                return out
    out.final_bound = {k: v for k, v in work.items() if k != "result"}
    return out
