from __future__ import annotations

import argparse
import json
import sys

from sparkrules.dmn import (
    DmnParseError,
    counterfactual_dmn_decision_table_xml,
    evaluate_dmn_decision_table_xml,
)
from sparkrules.ide import analyze_drl_for_lsp
from sparkrules.model.decision_table import CollectAggregateError, OverlappingRowsError
from sparkrules.parser import parse
from sparkrules.runtime import ChaosPolicy, run_chaos_scenario
from sparkrules.sim.simulator import ChainSimulationResult, RuleSimulator


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _resolve_drl(args: argparse.Namespace) -> str:
    if args.file:
        return _read_text(args.file)
    return str(args.drl or "")


def _resolve_xml(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return _read_text(str(args.file))
    return str(getattr(args, "xml", "") or "")


def _resolve_prefixed_drl(args: argparse.Namespace, prefix: str) -> str:
    pfile = getattr(args, f"{prefix}_file", None)
    if pfile:
        return _read_text(str(pfile))
    return str(getattr(args, f"{prefix}_drl", "") or "")


def _chain_simulation_to_dict(cr: ChainSimulationResult) -> dict[str, object]:
    c = cr.chain
    return {
        "any_fired": cr.any_fired,
        "last_fired": c.last_fired,
        "final_action": dict(c.final_action),
        "final_bound": dict(c.final_bound),
        "stop_reason": c.stop_reason,
        "steps": [
            {
                "rule_name": s.rule_name,
                "fired": s.fired,
                "skipped": s.skipped,
                "skip_reason": s.skip_reason,
                "action_output": dict(s.action_output),
                "stop_on_fire": s.stop_on_fire,
            }
            for s in c.steps
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sre-cli")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("health")

    validate = sub.add_parser("validate")
    vg = validate.add_mutually_exclusive_group(required=True)
    vg.add_argument("--drl")
    vg.add_argument("--file")

    simulate = sub.add_parser("simulate")
    sg = simulate.add_mutually_exclusive_group(required=True)
    sg.add_argument("--drl")
    sg.add_argument("--file")
    simulate.add_argument("--fact-json", default="{}")

    sim_chain = sub.add_parser("simulate-chain")
    schg = sim_chain.add_mutually_exclusive_group(required=True)
    schg.add_argument("--drl")
    schg.add_argument("--file")
    sim_chain.add_argument("--fact-json", default="{}")
    sim_chain.add_argument("--stop-on-decline", action="store_true")
    sim_chain.add_argument("--agenda-group-modes-json", default="{}")

    sim_shadow = sub.add_parser("simulate-shadow")
    pg = sim_shadow.add_mutually_exclusive_group(required=True)
    pg.add_argument("--primary-drl")
    pg.add_argument("--primary-file")
    sg = sim_shadow.add_mutually_exclusive_group(required=True)
    sg.add_argument("--shadow-drl")
    sg.add_argument("--shadow-file")
    sim_shadow.add_argument("--fact-json", default="{}")
    sim_shadow.add_argument("--run-id", default="shadow-cli")

    sim_cov = sub.add_parser("simulate-coverage")
    cvg = sim_cov.add_mutually_exclusive_group(required=True)
    cvg.add_argument("--drl")
    cvg.add_argument("--file")
    sim_cov.add_argument("--facts-json", required=True)

    chaos = sub.add_parser("chaos-check")
    chaos.add_argument("--fail-attempts", default="")
    chaos.add_argument("--max-retries", type=int, default=1)

    lsp = sub.add_parser("lsp-check")
    lg = lsp.add_mutually_exclusive_group(required=True)
    lg.add_argument("--drl")
    lg.add_argument("--file")
    lsp.add_argument("--prefix", default="")

    cf = sub.add_parser("counterfactual-check")
    cg = cf.add_mutually_exclusive_group(required=True)
    cg.add_argument("--drl")
    cg.add_argument("--file")
    cf.add_argument("--baseline-fact-json", required=True)
    cf.add_argument("--candidate-fact-json", required=True)

    dmn_ev = sub.add_parser("dmn-evaluate")
    dx = dmn_ev.add_mutually_exclusive_group(required=True)
    dx.add_argument("--xml", help="DMN decision table XML text")
    dx.add_argument("--file", help="Path to a file containing DMN XML")
    dmn_ev.add_argument("--env-json", default="{}")

    dmn_cf = sub.add_parser("dmn-counterfactual")
    cx = dmn_cf.add_mutually_exclusive_group(required=True)
    cx.add_argument("--xml", help="DMN decision table XML text")
    cx.add_argument("--file", help="Path to a file containing DMN XML")
    dmn_cf.add_argument("--base-env-json", default="{}")
    dmn_cf.add_argument("--patch-json", default="{}")

    cost = sub.add_parser(
        "cost",
        help="Rough batch cost heuristic (not a billing quote).",
    )
    cost.add_argument("--rows", type=float, default=1_000_000_000.0)
    cost.add_argument("--rules", type=int, default=50)
    cost.add_argument("--cluster", default="databricks")

    sk = sub.add_parser(
        "stream-kafka-iceberg",
        help="Print a stub Kafka → Iceberg structured-streaming plan (JSON).",
    )
    sk.add_argument("--topic", default="facts")
    sk.add_argument("--catalog", default="glue")
    sk.add_argument("--table", default="db.facts_scored")
    sk.add_argument("--checkpoint", default="s3://bucket/checkpoints/rules")
    sk.add_argument("--dry-run", action="store_true")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    if args.command == "health":
        sys.stdout.write(json.dumps({"status": "ok"}) + "\n")
        return 0
    if args.command == "cost":
        from sparkrules.tools.cost_estimate import estimate_batch_cost_usd

        out = estimate_batch_cost_usd(
            rows=float(args.rows),
            rules=int(args.rules),
            cluster=str(args.cluster),
        )
        sys.stdout.write(json.dumps(out) + "\n")
        return 0
    if args.command == "stream-kafka-iceberg":
        from sparkrules.tools.stream_kafka_iceberg import main as stream_main

        sk_argv: list[str] = [
            "--topic",
            str(args.topic),
            "--catalog",
            str(args.catalog),
            "--table",
            str(args.table),
            "--checkpoint",
            str(args.checkpoint),
        ]
        if bool(args.dry_run):
            sk_argv.append("--dry-run")
        return stream_main(sk_argv)
    if args.command == "validate":
        try:
            parse(_resolve_drl(args))
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"validate failed: {e}\n")
            return 2
        sys.stdout.write("ok\n")
        return 0
    if args.command == "simulate":
        try:
            fact = json.loads(args.fact_json)
            if not isinstance(fact, dict):
                raise ValueError("fact-json must decode to an object")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"invalid fact-json: {e}\n")
            return 2
        try:
            sim = RuleSimulator()
            out = sim.run(_resolve_drl(args), fact)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"simulate failed: {e}\n")
            return 2
        sys.stdout.write(
            json.dumps({"fired": out.fired, "action": out.action, "bound": out.bound}) + "\n"
        )
        return 0
    if args.command == "simulate-chain":
        try:
            fact = json.loads(args.fact_json)
            if not isinstance(fact, dict):
                raise ValueError("fact-json must decode to an object")
            modes = json.loads(args.agenda_group_modes_json)
            if not isinstance(modes, dict):
                raise ValueError("agenda-group-modes-json must decode to an object")
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in modes.items()):
                raise ValueError("agenda group modes must be string keys and string values")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"invalid json: {e}\n")
            return 2
        try:
            sim = RuleSimulator()
            cr = sim.run_chain(
                _resolve_drl(args),
                fact,
                stop_on_decline=bool(args.stop_on_decline),
                agenda_group_modes=dict(modes),
            )
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"simulate-chain failed: {e}\n")
            return 2
        sys.stdout.write(json.dumps(_chain_simulation_to_dict(cr), default=str) + "\n")
        return 0
    if args.command == "simulate-shadow":
        try:
            fact = json.loads(args.fact_json)
            if not isinstance(fact, dict):
                raise ValueError("fact-json must decode to an object")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"invalid fact-json: {e}\n")
            return 2
        try:
            sim = RuleSimulator()
            out = sim.run_shadow(
                _resolve_prefixed_drl(args, "primary"),
                _resolve_prefixed_drl(args, "shadow"),
                fact,
            )
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"simulate-shadow failed: {e}\n")
            return 2
        sys.stdout.write(
            json.dumps(
                {
                    "run_id": str(args.run_id or "shadow-cli"),
                    "primary_fired": out.primary.fired,
                    "primary_action": out.primary.action,
                    "shadow_fired": out.shadow.fired,
                    "shadow_action": out.shadow.action,
                    "drifted": out.drifted,
                    "drift_fields": list(out.drift_fields),
                },
                default=str,
            )
            + "\n",
        )
        return 0
    if args.command == "simulate-coverage":
        try:
            facts = json.loads(args.facts_json)
            if not isinstance(facts, list):
                raise ValueError("facts-json must decode to an array")
            for i, row in enumerate(facts):
                if not isinstance(row, dict):
                    raise ValueError(f"facts[{i}] must be an object")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"invalid facts-json: {e}\n")
            return 2
        try:
            sim = RuleSimulator()
            cov = sim.analyze_coverage(_resolve_drl(args), facts)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"simulate-coverage failed: {e}\n")
            return 2
        sys.stdout.write(
            json.dumps(
                {
                    "total_facts": cov.total_facts,
                    "total_rules": cov.total_rules,
                    "covered_rules": cov.covered_rules,
                    "items": [
                        {
                            "rule_name": it.rule_name,
                            "fired_count": it.fired_count,
                            "total": it.total,
                            "fire_rate": it.fire_rate,
                        }
                        for it in cov.items
                    ],
                },
                default=str,
            )
            + "\n",
        )
        return 0
    if args.command == "chaos-check":
        attempts = tuple(int(x.strip()) for x in str(args.fail_attempts).split(",") if x.strip())
        out = run_chaos_scenario(
            lambda: {"status": "ok"},
            ChaosPolicy(fail_on_attempts=attempts, max_retries=max(0, int(args.max_retries))),
        )
        sys.stdout.write(
            json.dumps(
                {
                    "ok": out.ok,
                    "attempts": out.attempts,
                    "injected_failures": out.injected_failures,
                    "events": list(out.events),
                }
            )
            + "\n"
        )
        return 0 if out.ok else 2
    if args.command == "lsp-check":
        out = analyze_drl_for_lsp(_resolve_drl(args), prefix=str(args.prefix or ""))
        sys.stdout.write(
            json.dumps(
                {
                    "diagnostics": [
                        {
                            "severity": d.severity,
                            "message": d.message,
                            "line": d.line,
                            "col": d.col,
                        }
                        for d in out.diagnostics
                    ],
                    "completions": list(out.completions),
                }
            )
            + "\n"
        )
        return 0
    if args.command == "counterfactual-check":
        try:
            baseline = json.loads(args.baseline_fact_json)
            candidate = json.loads(args.candidate_fact_json)
            if not isinstance(baseline, dict) or not isinstance(candidate, dict):
                raise ValueError("facts must decode to objects")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"invalid fact-json: {e}\n")
            return 2
        try:
            sim = RuleSimulator()
            b = sim.run(_resolve_drl(args), baseline)
            c = sim.run(_resolve_drl(args), candidate)
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"counterfactual failed: {e}\n")
            return 2
        keys = sorted(set(b.action) | set(c.action))
        drift = [k for k in keys if b.action.get(k) != c.action.get(k)]
        sys.stdout.write(
            json.dumps(
                {
                    "baseline_fired": b.fired,
                    "baseline_action": b.action,
                    "candidate_fired": c.fired,
                    "candidate_action": c.action,
                    "drifted": bool(drift),
                    "drift_fields": drift,
                }
            )
            + "\n"
        )
        return 0
    if args.command == "dmn-evaluate":
        try:
            env = json.loads(args.env_json)
            if not isinstance(env, dict):
                raise ValueError("env-json must decode to an object")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"invalid env-json: {e}\n")
            return 2
        try:
            result = evaluate_dmn_decision_table_xml(_resolve_xml(args), env)
        except DmnParseError as e:
            sys.stderr.write(f"dmn parse error: {e}\n")
            return 2
        except (CollectAggregateError, OverlappingRowsError) as e:
            sys.stderr.write(f"dmn evaluate error: {e}\n")
            return 2
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"dmn evaluate failed: {e}\n")
            return 2
        sys.stdout.write(json.dumps({"result": result}, default=str) + "\n")
        return 0
    if args.command == "dmn-counterfactual":
        try:
            base_env = json.loads(args.base_env_json)
            patch = json.loads(args.patch_json)
            if not isinstance(base_env, dict) or not isinstance(patch, dict):
                raise ValueError("base-env-json and patch-json must decode to objects")
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"invalid json: {e}\n")
            return 2
        try:
            out = counterfactual_dmn_decision_table_xml(_resolve_xml(args), base_env, patch)
        except DmnParseError as e:
            sys.stderr.write(f"dmn parse error: {e}\n")
            return 2
        except (CollectAggregateError, OverlappingRowsError) as e:
            sys.stderr.write(f"dmn counterfactual error: {e}\n")
            return 2
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"dmn counterfactual failed: {e}\n")
            return 2
        sys.stdout.write(json.dumps(out, default=str) + "\n")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
