"""OpenAI-compatible HTTP provider for :class:`sparkrules.ai.service.AiService`.

Enable with ``SPARKRULES_AI_PROVIDER=openai`` and ``SPARKRULES_OPENAI_API_KEY``.
Optional: ``SPARKRULES_OPENAI_BASE_URL`` (default ``https://api.openai.com/v1``),
``SPARKRULES_OPENAI_MODEL`` (default ``gpt-4o-mini``).

Uses stdlib :mod:`urllib` so the core package does not require ``httpx``.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name, "") or default).strip()


def _chat_completion_json(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(_env("SPARKRULES_OPENAI_TIMEOUT_SECONDS", "60") or "60")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — configurable URL
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenAI request failed: {e}") from e
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"OpenAI response envelope not JSON: {e}") from e
    if not isinstance(raw, dict):
        raise RuntimeError("OpenAI response must be a JSON object")
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI response missing choices")
    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(msg, dict):
        raise RuntimeError("OpenAI choice missing message")
    content = msg.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenAI message content empty")
    try:
        return json.loads(content.strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"OpenAI message was not valid JSON: {e}") from e


def _chat_completion_text(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body: dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.2}
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    timeout = float(_env("SPARKRULES_OPENAI_TIMEOUT_SECONDS", "60") or "60")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"OpenAI request failed: {e}") from e
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"OpenAI response envelope not JSON: {e}") from e
    if not isinstance(raw, dict):
        raise RuntimeError("OpenAI response must be a JSON object")
    choices = raw.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("OpenAI response missing choices")
    msg = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(msg, dict):
        raise RuntimeError("OpenAI choice missing message")
    content = msg.get("content")
    return str(content or "").strip()


def _normalize_rule_rows(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        rows = obj
    elif isinstance(obj, dict):
        for key in ("rules", "suggestions", "candidates", "items"):
            v = obj.get(key)
            if isinstance(v, list):
                rows = v
                break
        else:
            return []
    else:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        h = row.get("rule_handle")
        drl = row.get("drl")
        if isinstance(h, str) and isinstance(drl, str) and drl.strip():
            out.append({"rule_handle": h.strip(), "drl": drl.strip()})
    return out


def _normalize_dq_items(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, list):
        items = obj
    elif isinstance(obj, dict):
        items = obj.get("items")
        if not isinstance(items, list):
            return []
    else:
        return []
    out: list[dict[str, Any]] = []
    for row in items:
        if isinstance(row, dict) and isinstance(row.get("kind"), str) and isinstance(row.get("field"), str):
            out.append(dict(row))
    return out


@dataclass
class OpenAiHttpAiProvider:
    """OpenAI Chat Completions API (or compatible gateway) backing :class:`sparkrules.ai.service.AiService`."""

    api_key: str
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4o-mini"
    provider_name: str = "openai"

    def suggest_rules(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        system = (
            "You are a senior rules author for SparkRules (Drools-style DRL). "
            "Return JSON only with shape {\"rules\":[{\"rule_handle\":\"snake_case_id\",\"drl\":\"full single rule ... end\"}]} "
            "Each drl must be one complete rule block suitable for SparkRules."
        )
        user = json.dumps(payload, sort_keys=True, default=str)
        data = _chat_completion_json(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        rows = _normalize_rule_rows(data)
        if not rows:
            raise RuntimeError("OpenAI returned no usable rule suggestions (expected rules[].rule_handle + drl)")
        return rows

    def mine_dq_rules(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        system = (
            "You propose data-quality checks as JSON only: {\"items\":[{\"kind\":\"not_null|range|...\","
            "\"field\":\"name\", \"severity\":\"WARN|ERROR\", ...}]}. "
            "Use kinds compatible with SparkRules DQ checks."
        )
        user = json.dumps(payload, sort_keys=True, default=str)
        data = _chat_completion_json(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        items = _normalize_dq_items(data)
        if not items:
            raise RuntimeError("OpenAI returned no DQ items")
        return items

    def analyze_drift(self, payload: dict[str, Any]) -> dict[str, Any]:
        system = (
            "Return JSON only describing drift between rule versions or datasets: "
            "{\"status\":\"ok|warn\",\"drift_score\":0.0-1.0,\"note\":\"short summary\"}."
        )
        user = json.dumps(payload, sort_keys=True, default=str)
        return _chat_completion_json(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )

    def explain_rule(self, payload: dict[str, Any]) -> str:
        system = (
            "Explain SparkRules/Drools-style DRL for a compliance reviewer. "
            "Be concise; plain text only (no JSON)."
        )
        user = json.dumps(payload, sort_keys=True, default=str)
        return _chat_completion_text(
            api_key=self.api_key,
            base_url=self.base_url,
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )


def openai_provider_from_env() -> OpenAiHttpAiProvider | None:
    """Build provider from env, or ``None`` if API key is missing."""
    key = _env("SPARKRULES_OPENAI_API_KEY")
    if not key:
        return None
    return OpenAiHttpAiProvider(
        api_key=key,
        base_url=_env("SPARKRULES_OPENAI_BASE_URL", "https://api.openai.com/v1")
        or "https://api.openai.com/v1",
        model=_env("SPARKRULES_OPENAI_MODEL", "gpt-4o-mini") or "gpt-4o-mini",
    )
