"""JSON helpers for persisting :class:`sparkrules.model.rule.Rule` in SQL backends."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sparkrules.model.rule import Pass, Rule, RuleDefinition, RuleFormat


def rule_to_json(r: Rule) -> str:
    d = _rule_to_plain(r)
    return json.dumps(d, sort_keys=True, default=str)


def rule_from_json(blob: str) -> Rule:
    d = json.loads(blob)
    return _rule_from_plain(d)


def _rule_to_plain(r: Rule) -> dict[str, Any]:
    rd = r.rule_definition
    return {
        "rule_id": str(r.rule_id),
        "rule_handle": r.rule_handle,
        "version": r.version,
        "rule_group": r.rule_group,
        "salience": r.salience,
        "effective_from": r.effective_from.isoformat(),
        "effective_to": r.effective_to.isoformat() if r.effective_to else None,
        "is_active": r.is_active,
        "rule_definition": {
            "source": rd.source,
            "format": rd.format.name,
        },
        "activation_group": r.activation_group,
        "reason_codes": list(r.reason_codes),
        "pass_": r.pass_.name,
        "group_by_keys": list(r.group_by_keys),
        "source_file_hash": r.source_file_hash,
        "author_principal": r.author_principal,
        "namespace": r.namespace,
        "created_at": r.created_at.isoformat(),
    }


def _rule_from_plain(d: dict[str, Any]) -> Rule:
    rdef = d["rule_definition"]
    return Rule(
        rule_id=UUID(d["rule_id"]),
        rule_handle=d["rule_handle"],
        version=int(d["version"]),
        rule_group=d["rule_group"],
        salience=int(d["salience"]),
        effective_from=datetime.fromisoformat(d["effective_from"]),
        effective_to=(datetime.fromisoformat(d["effective_to"]) if d.get("effective_to") else None),
        is_active=bool(d["is_active"]),
        rule_definition=RuleDefinition(
            source=rdef["source"],
            format=RuleFormat[rdef["format"]],
        ),
        activation_group=d.get("activation_group"),
        reason_codes=tuple(d.get("reason_codes") or ()),
        pass_=Pass[d["pass_"]],
        group_by_keys=tuple(d.get("group_by_keys") or ()),
        source_file_hash=d.get("source_file_hash"),
        author_principal=str(d.get("author_principal") or "system"),
        namespace=str(d.get("namespace") or "default"),
        created_at=datetime.fromisoformat(d["created_at"]),
    )
