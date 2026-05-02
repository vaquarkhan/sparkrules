"""Optional online feature enrichment via Tecton's HTTP Python client (`tecton_client`).

Mirrors :mod:`sparkrules.integrations.feast_client`: callers can merge vectors into facts with
:class:`sparkrules.integrations.feast_client.merge_features_into_fact`.
Production paths use ``TectonClient.get_features`` → ``get_features_dict()`` per Tecton's docs.

See: https://docs.tecton.ai/docs/reading-feature-data/reading-feature-data-for-inference/reading-online-features-for-inference-using-the-python-client
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping



@dataclass
class TectonFeatureClient:
    """Thin wrapper so SparkRules can call Tecton without a hard dependency at import time.

    Either inject ``_client`` (must expose ``get_features``), or supply ``url`` + ``api_key``
    so a real :class:`tecton_client.TectonClient` is constructed on first use.
    """

    url: str | None = None
    api_key: str | None = None
    default_workspace_name: str | None = None
    feature_service_name: str | None = None
    _client: Any = field(default=None, repr=False)

    def _resolve_client(self) -> Any:
        if self._client is not None:
            return self._client
        if not self.url or not self.api_key:
            raise ValueError(
                "TectonFeatureClient requires url + api_key, or inject _client.",
            )
        try:
            from tecton_client import TectonClient  # type: ignore[import-untyped]
        except ImportError as e:
            raise RuntimeError(
                "Tecton HTTP client requires: pip install tecton-client (sparkrules[tecton])",
            ) from e

        kw: dict[str, Any] = {"url": self.url, "api_key": self.api_key}
        if self.default_workspace_name:
            kw["default_workspace_name"] = self.default_workspace_name
        self._client = TectonClient(**kw)
        return self._client

    def get_inference_features(
        self,
        *,
        feature_service_name: str | None = None,
        join_key_map: Mapping[str, Any] | None = None,
        request_context_map: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call Tecton's get-features endpoint for one logical row (join keys + optional context)."""
        svc = feature_service_name or self.feature_service_name
        if not svc:
            raise ValueError(
                "feature_service_name required (argument or client.feature_service_name).",
            )
        cli = self._resolve_client()
        resp = cli.get_features(
            feature_service_name=svc,
            join_key_map=dict(join_key_map or {}),
            request_context_map=dict(request_context_map or {}),
        )
        features_dict_fn = getattr(resp, "get_features_dict", None)
        if callable(features_dict_fn):
            out = features_dict_fn()
            return dict(out) if out is not None else {}
        res = getattr(resp, "result", None)
        feats = getattr(res, "features", None) if res is not None else None
        if isinstance(feats, dict):
            return feats
        return {}


def tecton_fetch_row(
    client: TectonFeatureClient | None,
    *,
    feature_service_name: str | None = None,
    join_key_field: str,
    join_value: Any,
    request_context_map: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Fetch one row of features keyed by ``join_key_field``, or `{}` when ``client`` is None."""
    if client is None:
        return {}
    return client.get_inference_features(
        feature_service_name=feature_service_name,
        join_key_map={join_key_field: join_value},
        request_context_map=request_context_map,
    )


