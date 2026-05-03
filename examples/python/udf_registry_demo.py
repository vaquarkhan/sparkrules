"""Register versioned pure UDFs and resolve the latest active definition.

Uses :class:`sparkrules.runtime.UserDefinedFunctionRegistry` and
:func:`sparkrules.runtime.eval_registered_pure_udf`.

  python examples/python/udf_registry_demo.py
"""

from __future__ import annotations

from datetime import UTC, datetime

from sparkrules.runtime import (
    UdfDefinition,
    UserDefinedFunctionRegistry,
    eval_registered_pure_udf,
)


def main() -> None:
    reg = UserDefinedFunctionRegistry()
    t0 = datetime(2025, 6, 1, tzinfo=UTC)
    reg.register(
        UdfDefinition(
            function_name="agg",
            version=1,
            input_signature=("int", "int"),
            return_type="int",
            pure=True,
            body="sum",
            active=True,
            activated_at=t0,
        )
    )
    reg.register(
        UdfDefinition(
            function_name="agg",
            version=2,
            input_signature=("int", "int"),
            return_type="int",
            pure=True,
            body="sum",
            active=True,
            activated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
    )
    latest = reg.resolve_latest_active("agg")
    at_old = reg.resolve_at_time("agg", datetime(2025, 12, 1, tzinfo=UTC))
    print("latest_active v", latest.version, "->", eval_registered_pure_udf(latest, (2, 3)))
    print("at 2025-12 v", at_old.version, "->", eval_registered_pure_udf(at_old, (2, 3)))


if __name__ == "__main__":
    main()
