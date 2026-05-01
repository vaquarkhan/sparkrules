from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Response
from prometheus_client import Counter, REGISTRY, generate_latest


class SreMetrics:
    def __init__(self) -> None:
        self.rules_fired = Counter(
            "sparkrules_rules_fired", "Rules fired", ["run_id"]
        )


def metrics_endpoint_app(registry: Any = REGISTRY) -> FastAPI:
    app = FastAPI()

    @app.get("/metrics")
    def m() -> Response:
        return Response(
            generate_latest(registry), media_type="text/plain"
        )
    return app
