"""DMN 1.3 minimal XML import (Camunda-flavored boxed decision tables, literal inputs).

Subset only—full FEEL plus DMN-TCK is future work.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any
from xml.etree import ElementTree as ET

from sparkrules.model.decision_table import (
    ColumnType,
    DecisionTable,
    HitPolicy,
    InputColumn,
    OutputColumn,
    Row,
    evaluate_decision_table,
)


class DmnParseError(ValueError):
    pass


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if tag.startswith("{") else tag


def _text_cell(parent: ET.Element) -> str:
    for child in parent.iter():
        if _local(child.tag).lower() == "text" and child.text:
            return child.text.strip()
    return ""


def _strip_feel(s: str) -> str:
    s = s.strip()
    if s in {"-", "", "NA", "null"}:
        return "*"
    m = re.match(r'^"(.*)"$', s)
    if m:
        return m.group(1)
    return s


def _guess_cell_type(txt: str) -> ColumnType:
    tl = txt.lower()
    if tl in {"true", "false"}:
        return ColumnType.BOOL
    try:
        int(txt)
        return ColumnType.INT
    except ValueError:
        pass
    try:
        float(txt)
        return ColumnType.FLOAT
    except ValueError:
        return ColumnType.STRING


def _hit_from_label(raw: str | None) -> HitPolicy:
    if not raw:
        return HitPolicy.UNIQUE
    u = raw.strip().upper().replace(" ", "").replace("_", "")
    if u.startswith("FIRST"):
        return HitPolicy.FIRST
    # DMN "rule order"  -  first hit in definition order (same as our FIRST evaluator).
    if u.startswith("RULEORDER"):
        return HitPolicy.FIRST
    # Output-order family (DMN 1.x): full semantics need output-key ordering; we approximate.
    if u.startswith("OUTPUTORDER"):
        return HitPolicy.COLLECT
    if u.startswith("OUTPUTFIRST"):
        return HitPolicy.FIRST
    if u.startswith("OUTPUTPRIORITY"):
        return HitPolicy.PRIORITY
    if u.startswith("COLLECTSUM"):
        return HitPolicy.COLLECT_SUM
    if u.startswith("COLLECTMIN"):
        return HitPolicy.COLLECT_MIN
    if u.startswith("COLLECTMAX"):
        return HitPolicy.COLLECT_MAX
    if u.startswith("COLLECTCOUNT"):
        return HitPolicy.COLLECT_COUNT
    if u.startswith("COLLECT"):
        return HitPolicy.COLLECT
    # Camunda / DMN-style "any"  -  return all matches (deterministic collect, not arbitrary pick).
    if u == "ANY":
        return HitPolicy.COLLECT
    if u.startswith("PRIORITY"):
        return HitPolicy.PRIORITY
    if u.startswith("UNIQUE"):
        return HitPolicy.UNIQUE
    return HitPolicy.UNIQUE


def _field_from_input(inp: ET.Element) -> str:
    for ch in inp.iter():
        if _local(ch.tag).lower() == "inputexpression":
            for it in ch.iter():
                if _local(it.tag).lower() != "text" or not it.text:
                    continue
                m = re.search(r"\$\s*\.\s*([A-Za-z0-9_]+)", it.text)
                return m.group(1) if m else "input"
            break
    return "input"


def parse_dmn_decision_table_xml(xml_text: str) -> DecisionTable:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        raise DmnParseError(str(e)) from e

    dtables: list[ET.Element] = []
    for el in root.iter():
        if _local(el.tag).lower().endswith("decisiontable"):
            dtables.append(el)
    if len(dtables) != 1:
        raise DmnParseError(f"expected exactly one decisionTable, found {len(dtables)}")
    dt = dtables[0]

    hit_policy = _hit_from_label(dt.get("hitPolicy"))

    inputs: list[InputColumn] = []
    outputs: list[OutputColumn] = []
    rules_out: list[Row] = []

    for inp in dt:
        if _local(inp.tag).lower().endswith("input"):
            name = (inp.get("label") or inp.get("id") or "in").strip()
            fld = _field_from_input(inp)
            inputs.append(
                InputColumn(name=name, field_ref=fld, col_type=ColumnType.STRING, operator=None)
            )
    for out in dt:
        tag = _local(out.tag).lower()
        if tag.endswith("output"):
            name = (out.get("name") or out.get("label") or out.get("id") or "out").strip()
            outputs.append(OutputColumn(name=name, field_ref=name, col_type=ColumnType.STRING))

    if not inputs or not outputs:
        raise DmnParseError("decisionTable must contain input and output elements")

    inferred_in_types: list[ColumnType] = []

    seen_rule = False
    for rule in dt:
        if _local(rule.tag).lower() != "rule":
            continue
        seen_rule = True
        cells: list[str] = []
        for cell in rule:
            lc = _local(cell.tag).lower()
            if lc.endswith("inputentry") or lc.endswith("outputentry"):
                cells.append(_strip_feel(_text_cell(cell)))
        if len(cells) != len(inputs) + len(outputs):
            raise DmnParseError("rule cell count mismatches DMN inputs/outputs")
        if not inferred_in_types:
            inferred_in_types = [_guess_cell_type(cells[i]) for i in range(len(inputs))]
        pri = 0
        raw_pri = rule.get("priority")
        if raw_pri is not None and str(raw_pri).strip() != "":
            try:
                pri = int(str(raw_pri).strip())
            except ValueError:
                pri = 0
        rules_out.append(Row(cells=tuple(cells), priority=pri))
    if not seen_rule:
        raise DmnParseError("decisionTable has no rules")

    typed_inputs = tuple(
        InputColumn(ic.name, ic.field_ref, inferred_in_types[ix], ic.operator)
        for ix, ic in enumerate(inputs)
    )

    dec_name_el = None
    for el in root.iter():
        if _local(el.tag).lower().endswith("decision"):
            dec_name_el = el
            break
    tbl_name = (
        (dec_name_el.get("name") if dec_name_el is not None else None)
        or root.get("name")
        or root.get("id")
        or "dmn_decision"
    )

    return DecisionTable(
        name=str(tbl_name),
        hit_policy=hit_policy,
        input_columns=typed_inputs,
        output_columns=tuple(outputs),
        rows=tuple(rules_out),
    )


def evaluate_dmn_decision_table_xml(xml_text: str, env: Mapping[str, Any]) -> Any:
    """Parse minimal DMN XML then run :func:`sparkrules.model.decision_table.evaluate_decision_table`."""
    return evaluate_decision_table(parse_dmn_decision_table_xml(xml_text), env)


def counterfactual_dmn_decision_table_xml(
    xml_text: str,
    base_env: Mapping[str, Any],
    env_patch: Mapping[str, Any],
) -> dict[str, Any]:
    """Re-evaluate the same table for ``base_env`` vs ``{**base_env, **env_patch}`` (single parse).

    Draft helper for regulatory / explainability "what-if" flows—not a full causal counterfactual stack.
    """
    table = parse_dmn_decision_table_xml(xml_text)
    merged = dict(base_env)
    merged.update(env_patch)
    base_out = evaluate_decision_table(table, base_env)
    cf_out = evaluate_decision_table(table, merged)
    return {
        "base": base_out,
        "counterfactual": cf_out,
        "patch": dict(env_patch),
        "outputs_differ": base_out != cf_out,
    }

