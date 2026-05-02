"""Hydrating rule-metadata store that mirrors writes to an external sink (e.g. Iceberg append).

Lakehouse ingestion can plug ``version_sink(blob_json, rule_handle, version)`` via
:class:`IcebergHydratingRuleStore` while preserving the metadata API.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sparkrules.model.rule import Rule
from sparkrules.store.metadata_store import InMemoryRuleMetadataStore
from sparkrules.store.rule_serialization import rule_to_json


class IcebergHydratingRuleStore(InMemoryRuleMetadataStore):
    """Writes through to :class:`InMemoryRuleMetadataStore` and notifies ``version_sink``."""

    def __init__(self, *, version_sink: Callable[[str, str, int], Any] | None = None):
        super().__init__()
        self._version_sink = version_sink

    def _emit(self, r: Rule) -> None:
        if self._version_sink:
            self._version_sink(rule_to_json(r), r.rule_handle, r.version)

    def insert(self, r: Rule) -> Rule:
        out = super().insert(r)
        self._emit(out)
        return out

    def update(self, rule_handle: str, patch: Rule) -> Rule:
        out = super().update(rule_handle, patch)
        self._emit(out)
        return out
