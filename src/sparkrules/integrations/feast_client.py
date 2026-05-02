"""Optional online feature enrichment via Feast (stub-friendly)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, MutableMapping, Sequence


@dataclass
class FeastFeatureClient:
    """Thin wrapper so SparkRules can call Feast without hard dependency at import time.

    Pass ``store`` for in-process tests; otherwise ``get_feature_store()`` is attempted on use.
    """

    repo_path: str | None = None
    _store: Any = field(default=None, repr=False)

    def _resolve_store(self) -> Any:
        if self._store is not None:
            return self._store
        if not self.repo_path:
            raise ValueError("FeastFeatureClient requires repo_path or an injected store")
        try:
            from feast import FeatureStore  # type: ignore[import-untyped]
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("feast features require: pip install feast") from e
        self._store = FeatureStore(repo_path=self.repo_path)
        return self._store

    def get_online_features(
        self,
        *,
        features: Sequence[str],
        entity_rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        st = self._resolve_store()
        fv = st.get_online_features(features=list(features), entity_rows=entity_rows)
        to_d = getattr(fv, "to_dict", None)
        if callable(to_d):
            return to_d()
        df = getattr(fv, "to_df", lambda: fv)()
        if hasattr(df, "to_dict"):
            return df.to_dict(orient="list")  # type: ignore[no-any-return]
        return dict(fv)  # type: ignore[arg-type,call-overload]


def feast_fetch_row(
    client: FeastFeatureClient | None,
    *,
    features: Sequence[str],
    entity_id_field: str,
    entity_id: str,
) -> dict[str, Any]:
    """Return one feature vector as a flat dict, or empty if ``client`` is None."""
    if client is None:
        return {}
    raw = client.get_online_features(
        features=features,
        entity_rows=[{entity_id_field: entity_id}],
    )
    out: dict[str, Any] = {}
    for k, v in raw.items():
        if isinstance(v, list) and v:
            out[k] = v[0]
        else:
            out[k] = v
    return out


def merge_features_into_fact(
    fact: MutableMapping[str, Any],
    features: Mapping[str, Any],
    *,
    prefix: str = "feat_",
) -> None:
    for k, v in features.items():
        fact[prefix + k.replace("-", "_")] = v
