from __future__ import annotations

from datetime import UTC, datetime

from sre.store import InMemoryRuleMetadataStore, UnknownRuleError


def sync_dev_from_active(
    store: InMemoryRuleMetadataStore,
    reg: PromotionRegistry,
    namespace: str,
    rule_handle: str,
) -> int:
    """Set the dev pin to the current time-active version for the handle."""
    t = datetime.now(UTC)
    r = store.resolve(rule_handle, t)
    if r is None:
        raise ValueError("no active rule for that handle at the current time")
    if r.namespace != namespace:
        raise ValueError("namespace does not match the active rule's namespace")
    reg.set_pin(namespace, rule_handle, "dev", r.version)
    return r.version


def validate_version_namespace(
    store: InMemoryRuleMetadataStore, namespace: str, rule_handle: str, version: int
) -> None:
    try:
        r = store.get(rule_handle, version)
    except UnknownRuleError as e:
        raise ValueError("rule version not in store") from e
    if r.namespace != namespace:
        raise ValueError("namespace does not match the stored rule's namespace")
