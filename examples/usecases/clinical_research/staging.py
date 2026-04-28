# Author: Vaquar Khan
"""Build nested fact ``f`` + derived columns for clinical trial harmonization demos.

Normalization math lives here (upstream ETL or dbt staging would do the same);
DRL expresses **classification, dedupe policy, and field promotion** onto ``result.*``.
"""

from __future__ import annotations

import re
from typing import Any


def _to_float(raw: Any) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def enrich_clinical_flat(rec: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of *rec* suitable for nesting under ``f`` with enrichment fields."""

    row = {k: (v.strip() if isinstance(v, str) else v) for k, v in rec.items()}
    nv = _to_float(row.get("raw_value"))
    mc = row.get("measure_code") or ""
    unit = (row.get("raw_unit") or "").strip()

    row["numeric_value"] = nv
    row["dup_key"] = row.get("dup_key") or ""
    row["dup_note"] = row.get("dup_note") or ""
    row["is_repeat_of_record"] = row.get("is_repeat_of_record") or ""
    row["repeat_note"] = (
        row.get("repeat_note")
        or "Repeat draw linked to primary record (retest / protocol)."
    )

    # Deterministic normalization hints (canonical numerics consumed by rules).
    row["wt_pref_kg"] = None
    row["conv_factor_lb_to_kg"] = None
    if nv is not None and mc == "WT" and unit.lower() == "lb":
        kg = nv / 2.2046226218
        row["wt_pref_kg"] = round(kg + 1e-12, 3)
        row["conv_factor_lb_to_kg"] = nv / kg if kg else None

    row["glucose_pref_mgdl"] = None
    row["conv_factor_mmol_to_mgdl"] = None
    if nv is not None and mc == "GLUCOSE" and unit.lower() == "mmol/l":
        mg = nv * 18.0182
        row["glucose_pref_mgdl"] = round(mg + 1e-12, 1)
        row["conv_factor_mmol_to_mgdl"] = mg / nv if nv else None

    row["hgb_pref_gdl"] = None
    row["conv_factor_gl_per_gdl"] = None
    if nv is not None and mc == "HGB" and re.match(r"(?i)^g/L$", unit):
        gdl = nv / 10.0
        row["hgb_pref_gdl"] = round(gdl + 1e-12, 2)
        row["conv_factor_gl_per_gdl"] = nv / gdl if gdl else None

    row["alt_pref_kul"] = None
    row["conv_factor_ul_to_kul"] = None
    if nv is not None and mc == "ALT" and re.match(r"(?i)^U/L$", unit):
        kul = nv / 1000.0
        row["alt_pref_kul"] = round(kul + 1e-12, 3)
        row["conv_factor_ul_to_kul"] = nv / kul if kul else None
    return row


def flatten_for_iter(record_id_field: str, rec: dict[str, Any]) -> dict[str, Any]:
    enriched = enrich_clinical_flat(rec)
    rid = enriched.pop(record_id_field, "")
    nested = enriched
    return {"record_id": str(rid), "f": nested}
