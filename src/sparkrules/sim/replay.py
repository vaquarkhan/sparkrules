from __future__ import annotations

from dataclasses import dataclass

from sparkrules.runtime.batch import RunRecord


class MissingRuleSetVersionError(KeyError):
    pass


@dataclass
class ReplayService:
    def replay(
        self, run: RunRecord, expected_version: str
    ) -> str:
        if run.rule_set_version != expected_version:
            raise MissingRuleSetVersionError(expected_version)
        return run.run_id
