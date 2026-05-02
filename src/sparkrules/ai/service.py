from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol


class AiProvider(Protocol):
    provider_name: str

    def suggest_rules(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...

    def mine_dq_rules(self, payload: dict[str, Any]) -> list[dict[str, Any]]: ...

    def analyze_drift(self, payload: dict[str, Any]) -> dict[str, Any]: ...

    def explain_rule(self, payload: dict[str, Any]) -> str: ...


def _stub_explain_from_drl(payload: dict[str, Any]) -> str:
    from sparkrules.parser import parse
    from sparkrules.parser.ast import ParseError

    if not isinstance(payload, dict):
        return (
            'Explain-rule expects a JSON object with a string "drl" field '
            "(offline structural mode — set SPARKRULES_AI_PROVIDER=openai for generative explanations)."
        )
    raw = payload.get("drl")
    if raw is not None and not isinstance(raw, str):
        return (
            'Field "drl" must be a string of DRL source '
            "(offline structural mode — no generative model)."
        )
    drl = str(raw or "").strip()
    if not drl:
        return (
            'No DRL text was provided: send a non-empty "drl" string '
            "(offline structural mode — no generative model)."
        )
    try:
        r = parse(drl)
    except ParseError as e:
        return (
            "DRL failed to parse, so the rule cannot be summarized yet "
            f"(offline structural mode). ParseError: {e}"
        )
    except Exception as e:  # noqa: BLE001
        return (
            "DRL triggered an unexpected error during parse/analysis "
            f"(offline structural mode): {type(e).__name__}: {e}"
        )
    return (
        f"Parsed rule `{r.name}` (offline structural summary): salience {r.salience}, "
        f"stop_on_fire={getattr(r, 'stop_on_fire', False)}. "
        "When-clauses are evaluated against your fact JSON; then-actions populate result.*. "
        "Set SPARKRULES_AI_PROVIDER=openai and SPARKRULES_OPENAI_API_KEY for model-backed text."
    )


def redact_payload(payload: dict[str, Any], pii_fields: set[str]) -> dict[str, Any]:
    def _mask(k: str, v: Any) -> Any:
        if k in pii_fields:
            return hashlib.sha256(str(v).encode("utf-8")).hexdigest()
        if isinstance(v, dict):
            return {kk: _mask(kk, vv) for kk, vv in v.items()}
        if isinstance(v, list):
            return [_mask(k, x) for x in v]
        return v

    return {k: _mask(k, v) for k, v in payload.items()}


@dataclass(frozen=True, slots=True)
class AiSuggestion:
    id: str
    kind: str
    namespace: str
    rule_handle: str
    drl: str
    is_active: bool
    source: str
    simulator_result: dict[str, Any] | None
    created_at: str
    status: str = "PENDING"
    model_id: str = "stub-model"
    principal: str = "system"
    prompt_hash: str = ""
    response_hash: str = ""


@dataclass
class AiSuggestionStore:
    items: dict[str, AiSuggestion] = field(default_factory=dict)

    def upsert(self, s: AiSuggestion) -> None:
        self.items[s.id] = s

    def list_pending(self) -> list[AiSuggestion]:
        return sorted(
            [x for x in self.items.values() if x.status == "PENDING"],
            key=lambda x: (x.created_at, x.id),
        )

    def get(self, sid: str) -> AiSuggestion:
        if sid not in self.items:
            raise KeyError(sid)
        return self.items[sid]


def create_default_ai_provider() -> AiProvider:
    """Pick an :class:`AiProvider` from ``SPARKRULES_AI_PROVIDER`` (default: offline stub).

    ``openai`` / ``openai_http`` / ``openai-compatible`` select :class:`sparkrules.ai.openai_provider.OpenAiHttpAiProvider`
    when ``SPARKRULES_OPENAI_API_KEY`` is set; otherwise falls back to :class:`StubAiProvider`.
    """
    mode = (os.environ.get("SPARKRULES_AI_PROVIDER", "") or "stub").strip().lower()
    if mode in ("openai", "openai_http", "openai-compatible"):
        from sparkrules.ai.openai_provider import openai_provider_from_env

        p = openai_provider_from_env()
        if p is not None:
            return p
    return StubAiProvider()


@dataclass
class StubAiProvider:
    provider_name: str = "stub"

    def suggest_rules(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        h = str(payload.get("rule_handle") or "ai_rule")
        return [
            {
                "rule_handle": h + "_ai",
                "drl": f"rule {h}_ai when $t : T ( true ) then result.ai = true; end",
            }
        ]

    def mine_dq_rules(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        field = str(payload.get("field") or "id")
        return [
            {
                "kind": "not_null",
                "field": field,
                "severity": "WARN",
            }
        ]

    def analyze_drift(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "ok",
            "drift_score": 0.0,
            "note": (
                "offline placeholder (no model). "
                "Set SPARKRULES_AI_PROVIDER=openai and SPARKRULES_OPENAI_API_KEY for scored drift."
            ),
        }

    def explain_rule(self, payload: dict[str, Any]) -> str:
        return _stub_explain_from_drl(payload)


@dataclass
class AiService:
    provider: AiProvider
    store: AiSuggestionStore = field(default_factory=AiSuggestionStore)
    pii_fields: set[str] = field(default_factory=set)

    def _hash(self, obj: object) -> str:
        raw = json.dumps(obj, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def create_rule_suggestions(
        self,
        *,
        namespace: str,
        payload: dict[str, Any],
        principal: str,
    ) -> list[AiSuggestion]:
        red = redact_payload(payload, self.pii_fields)
        prompt_hash = self._hash(red)
        raw = self.provider.suggest_rules(red)
        out: list[AiSuggestion] = []
        for i, it in enumerate(raw):
            sid = f"ai-{self._hash([namespace, it, i])[:12]}"
            s = AiSuggestion(
                id=sid,
                kind="RULE",
                namespace=namespace,
                rule_handle=str(it["rule_handle"]),
                drl=str(it["drl"]),
                is_active=False,
                source="AI_SUGGESTION",
                simulator_result={"required": True, "ok": False},
                created_at=datetime.now(UTC).isoformat(),
                principal=principal,
                prompt_hash=prompt_hash,
                response_hash=self._hash(it),
                model_id=getattr(self.provider, "provider_name", "provider"),
            )
            self.store.upsert(s)
            out.append(s)
        return out

    def approve(self, sid: str) -> AiSuggestion:
        s = self.store.get(sid)
        if not s.simulator_result or not bool(s.simulator_result.get("ok")):
            raise ValueError("simulator evidence required before approval")
        upd = replace(s, status="APPROVED")
        self.store.upsert(upd)
        return upd

    def record_simulation_evidence(
        self,
        sid: str,
        *,
        fired: bool,
        action: dict[str, Any],
        bound: dict[str, Any],
    ) -> AiSuggestion:
        s = self.store.get(sid)
        if s.status != "PENDING":
            raise ValueError("only PENDING suggestions accept simulation evidence")
        sim: dict[str, Any] = {
            "required": True,
            "ok": True,
            "fired": fired,
            "action": action,
            "bound": bound,
        }
        upd = replace(s, simulator_result=sim)
        self.store.upsert(upd)
        return upd

    def reject(self, sid: str) -> AiSuggestion:
        s = self.store.get(sid)
        upd = replace(s, status="REJECTED")
        self.store.upsert(upd)
        return upd
