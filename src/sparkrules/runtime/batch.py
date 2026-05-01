from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from sparkrules.executor.rule_executor import FactResult, RuleExecutor
from sparkrules.model.rule import now_utc
from sparkrules.runtime.iceberg_store import Row


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    mode: str
    input_table_name: str
    input_snapshot_id: int | None
    rule_set_version: str
    config_fingerprint: str
    start_ts: datetime
    end_ts: datetime | None
    facts_processed: int
    rules_fired: int
    rules_errored: int
    status: str
    error_class: str | None
    error_message: str | None
    replay_source_run_id: str | None = None


@dataclass
class BatchEvaluationSpec:
    drl: str
    table_name: str
    fact_id_field: str = "id"


@dataclass
class BatchEvaluator:
    drl: str
    ex: RuleExecutor = field(default_factory=RuleExecutor)

    def run(
        self, rows: Sequence[Row], spec: BatchEvaluationSpec | None = None
    ) -> tuple[list[FactResult], RunRecord]:
        sp = spec or BatchEvaluationSpec(self.drl, "facts")
        rid = str(uuid.uuid4())
        t0 = now_utc()
        out: list[FactResult] = []
        fired, errs = 0, 0
        for r in rows:
            fid = str(r.get(sp.fact_id_field, "0"))
            m = {k: v for k, v in r.items() if k not in (sp.fact_id_field,)}
            fr = self.ex.run(
                m,
                sp.drl,
                fact_id=fid,
            )
            out.append(fr)
            if fr.fired:
                fired += 1
        return out, RunRecord(
            run_id=rid,
            mode="BATCH",
            input_table_name=sp.table_name,
            input_snapshot_id=None,
            rule_set_version="0",
            config_fingerprint="0",
            start_ts=t0,
            end_ts=now_utc(),
            facts_processed=len(rows),
            rules_fired=fired,
            rules_errored=errs,
            status="SUCCESS",
            error_class=None,
            error_message=None,
        )
