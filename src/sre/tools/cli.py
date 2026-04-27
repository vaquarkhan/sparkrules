from __future__ import annotations

import argparse
import json
import sys

from sre.ide import analyze_drl_for_lsp
from sre.parser import parse
from sre.runtime import ChaosPolicy, run_chaos_scenario
from sre.sim import RuleSimulator


def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _resolve_drl(args: argparse.Namespace) -> str:
    if args.file:
        return _read_text(args.file)
    return str(args.drl or "")


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

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    if args.command == "health":
        sys.stdout.write(json.dumps({"status": "ok"}) + "\n")
        return 0
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
    if args.command == "chaos-check":
        attempts = tuple(
            int(x.strip()) for x in str(args.fail_attempts).split(",") if x.strip()
        )
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
    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
