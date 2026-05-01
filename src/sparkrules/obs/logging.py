from __future__ import annotations

import structlog


def configure_logging(*, json_only: bool = True) -> None:
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(key="ts", utc=True),
            structlog.processors.JSONRenderer()
            if json_only
            else structlog.dev.ConsoleRenderer(),
        ]
    )


def bind_run_context(run_id: str) -> structlog.BoundLogger:
    return structlog.get_logger().bind(run_id=run_id)


def get_logger(name: str = "sre") -> structlog.BoundLogger:
    return structlog.get_logger(name)
