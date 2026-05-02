from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum, auto
from typing import Any, Mapping, Sequence

from sparkrules.model.rule import now_utc


class HitPolicy(Enum):
    UNIQUE = auto()
    FIRST = auto()
    PRIORITY = auto()
    COLLECT = auto()
    COLLECT_SUM = auto()
    COLLECT_MIN = auto()
    COLLECT_MAX = auto()
    COLLECT_COUNT = auto()


class ColumnType(Enum):
    INT = "INT"
    FLOAT = "FLOAT"
    STRING = "STRING"
    BOOL = "BOOL"


@dataclass(frozen=True, slots=True)
class InputColumn:
    name: str
    field_ref: str
    col_type: ColumnType
    operator: str | None = None


@dataclass(frozen=True, slots=True)
class OutputColumn:
    name: str
    field_ref: str
    col_type: ColumnType


@dataclass(frozen=True, slots=True)
class Row:
    cells: tuple[Any, ...]
    priority: int = 0


@dataclass(frozen=True, slots=True)
class DecisionTable:
    name: str
    hit_policy: HitPolicy
    input_columns: tuple[InputColumn, ...]
    output_columns: tuple[OutputColumn, ...]
    rows: tuple[Row, ...]

    @property
    def has_priority_column(self) -> bool:
        return any(r.priority != 0 for r in self.rows)


class OverlappingRowsError(ValueError):
    pass


class CollectAggregateError(ValueError):
    """Invalid inputs for COLLECT_* aggregate evaluation (per-output column)."""


def _row_matches(row: Row, input_cols: Sequence[InputColumn], env: Mapping[str, Any]) -> bool:
    for i, col in enumerate(input_cols):
        if i >= len(row.cells):
            return False
        cell = row.cells[i]
        if cell is None or cell == "*":
            continue
        v = env.get(col.field_ref)
        op = col.operator or "=="
        if op == "==":
            if v != cell:
                return False
        elif op == "!=":
            if v == cell:
                return False
        elif op in ("<", "<=", ">", ">="):
            if v is None:
                return False
            a, b = v, cell
            if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                return False
            if op == "<" and not (a < b):
                return False
            if op == "<=" and not (a <= b):
                return False
            if op == ">" and not (a > b):
                return False
            if op == ">=" and not (a >= b):
                return False
        else:
            if v != cell:
                return False
    return True


def _merge_outputs(table: DecisionTable, row: Row, n_in: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for j, ocol in enumerate(table.output_columns):
        idx = n_in + j
        if idx < len(row.cells):
            out[ocol.name] = row.cells[idx]
    return out


def _is_real_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _coerce_aggregate_numbers(vals: list[Any], col_name: str) -> list[float]:
    """Coerce DMN literal outputs (often strings) to floats for SUM/MIN/MAX."""
    out: list[float] = []
    for v in vals:
        if _is_real_number(v):
            out.append(float(v))
            continue
        if isinstance(v, str):
            s = v.strip()
            try:
                out.append(float(s))
            except ValueError as e:
                raise CollectAggregateError(
                    f"COLLECT aggregate requires numeric values for {col_name!r}",
                ) from e
            continue
        raise CollectAggregateError(
            f"COLLECT aggregate requires numeric values for {col_name!r}",
        )
    return out


def _evaluate_collect_aggregate(
    table: DecisionTable, matches: list[Row], n_in: int, hp: HitPolicy
) -> dict[str, Any]:
    """DMN-style collect aggregators; each output column is aggregated independently."""
    if not table.output_columns:
        raise CollectAggregateError(
            "COLLECT_SUM, COLLECT_MIN, COLLECT_MAX, and COLLECT_COUNT require at least one output column",
        )
    merged = [_merge_outputs(table, r, n_in) for r in matches]
    result: dict[str, Any] = {}
    for ocol in table.output_columns:
        oname = ocol.name
        vals: list[Any] = []
        for d in merged:
            if oname not in d:
                raise CollectAggregateError(f"missing output {oname!r} on a matching row")
            vals.append(d[oname])
        if hp == HitPolicy.COLLECT_COUNT:
            result[oname] = len(matches)
        elif hp == HitPolicy.COLLECT_SUM:
            nums = _coerce_aggregate_numbers(vals, oname)
            result[oname] = sum(nums)
        elif hp == HitPolicy.COLLECT_MIN:
            nums = _coerce_aggregate_numbers(vals, oname)
            result[oname] = min(nums)
        else:
            nums = _coerce_aggregate_numbers(vals, oname)
            result[oname] = max(nums)
    return result


def evaluate_decision_table(
    table: DecisionTable, env: Mapping[str, Any]
) -> list[dict[str, Any]] | dict[str, Any] | None:
    matches: list[Row] = [r for r in table.rows if _row_matches(r, table.input_columns, env)]
    n_in = len(table.input_columns)
    if not matches:
        return None
    if table.hit_policy in (
        HitPolicy.COLLECT_SUM,
        HitPolicy.COLLECT_MIN,
        HitPolicy.COLLECT_MAX,
        HitPolicy.COLLECT_COUNT,
    ):
        return _evaluate_collect_aggregate(table, matches, n_in, table.hit_policy)
    if table.hit_policy == HitPolicy.COLLECT:
        return [_merge_outputs(table, r, n_in) for r in matches]
    if table.hit_policy == HitPolicy.FIRST:
        r = min(matches, key=lambda x: (table.rows.index(x), -x.priority))
        return _merge_outputs(table, r, n_in)
    if table.hit_policy == HitPolicy.PRIORITY:
        r = max(matches, key=lambda r: r.priority)
        return _merge_outputs(table, r, n_in)
    # UNIQUE
    if len(matches) > 1:
        raise OverlappingRowsError("more than one row matches for UNIQUE")
    r = matches[0]
    return _merge_outputs(table, r, n_in)


def _col_to_dict(
    c: InputColumn | OutputColumn,
) -> dict[str, Any]:
    d = asdict(c)
    d["col_type"] = c.col_type.name
    return d


def _input_from_dict(d: dict[str, Any]) -> InputColumn:
    return InputColumn(
        name=d["name"],
        field_ref=d["field_ref"],
        col_type=ColumnType[d["col_type"]]
        if d["col_type"] in ColumnType.__members__
        else ColumnType(d["col_type"]),
        operator=d.get("operator"),
    )


def _output_from_dict(d: dict[str, Any]) -> OutputColumn:
    return OutputColumn(
        name=d["name"],
        field_ref=d["field_ref"],
        col_type=ColumnType[d["col_type"]]
        if d["col_type"] in ColumnType.__members__
        else ColumnType(d["col_type"]),
    )


def dt_to_json(table: DecisionTable) -> str:
    payload = {
        "name": table.name,
        "hit_policy": table.hit_policy.name,
        "input_columns": [_col_to_dict(c) for c in table.input_columns],
        "output_columns": [_col_to_dict(c) for c in table.output_columns],
        "rows": [{"cells": list(r.cells), "priority": r.priority} for r in table.rows],
    }
    payload["__meta__"] = {"generated_at": now_utc().isoformat()}
    return json.dumps(payload, default=str)


def dt_from_json(s: str) -> DecisionTable:
    d = json.loads(s)
    hp = HitPolicy[d["hit_policy"]]
    inputs = tuple(_input_from_dict(c) for c in d["input_columns"])
    outputs = tuple(_output_from_dict(c) for c in d["output_columns"])
    rows = tuple(
        Row(cells=tuple(x["cells"]), priority=int(x.get("priority", 0))) for x in d["rows"]
    )
    return DecisionTable(
        name=d["name"],
        hit_policy=hp,
        input_columns=inputs,
        output_columns=outputs,
        rows=rows,
    )
