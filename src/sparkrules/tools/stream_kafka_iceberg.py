from __future__ import annotations

import argparse
import json
import sys


def build_stub_plan(
    *,
    topic: str,
    catalog: str,
    table: str,
    checkpoint: str,
) -> dict[str, object]:
    return {
        "source": {"kind": "kafka", "topic": topic},
        "sink": {"kind": "iceberg", "catalog": catalog, "table": table},
        "checkpoint_location": checkpoint,
        "note": "Stub plan only; wire Spark Structured Streaming in your deployment.",
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Kafka → Iceberg streaming stub (planning helper).")
    p.add_argument("--topic", default="facts")
    p.add_argument("--catalog", default="glue")
    p.add_argument("--table", default="db.facts_scored")
    p.add_argument("--checkpoint", default="s3://bucket/checkpoints/rules")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    plan = build_stub_plan(
        topic=args.topic,
        catalog=args.catalog,
        table=args.table,
        checkpoint=args.checkpoint,
    )
    sys.stdout.write(json.dumps({"dry_run": bool(args.dry_run), "plan": plan}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
