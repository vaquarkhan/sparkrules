from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Protocol


class ModelProvider(Protocol):
    provider_name: str

    def score(
        self,
        *,
        model_id: str,
        model_version: str,
        features: dict[str, Any],
    ) -> float: ...


@dataclass(frozen=True, slots=True)
class ModelInvocation:
    model_id: str
    model_version: str
    provider: str
    features: dict[str, Any]
    score: float
    explanation: dict[str, Any]


@dataclass
class StubModelProvider:
    provider_name: str = "stub-model-provider"

    def score(
        self,
        *,
        model_id: str,
        model_version: str,
        features: dict[str, Any],
    ) -> float:
        raw = json.dumps(
            {"model_id": model_id, "model_version": model_version, "features": features},
            sort_keys=True,
            default=str,
        )
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        n = int(h[:12], 16)
        return (n % 1000000) / 1000000.0


def invoke_model(
    provider: ModelProvider,
    *,
    model_id: str,
    model_version: str,
    features: dict[str, Any],
) -> ModelInvocation:
    s = provider.score(model_id=model_id, model_version=model_version, features=features)
    return ModelInvocation(
        model_id=model_id,
        model_version=model_version,
        provider=provider.provider_name,
        features=dict(features),
        score=float(s),
        explanation={
            "model_id": model_id,
            "model_version": model_version,
            "features": dict(features),
            "score": float(s),
        },
    )
