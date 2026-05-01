"""Settlement + replay (ladder: idea-brainstrom §8)."""
from __future__ import annotations

import pytest

from sparkrules.model.rule import now_utc
from sparkrules.runtime.batch import RunRecord
from sparkrules.sim.replay import MissingRuleSetVersionError, ReplayService

pytestmark = pytest.mark.integration


def test_replay_succeeds_matching_version() -> None:
    t0, t1 = now_utc(), now_utc()
    r = RunRecord(
        "run-a",
        "BATCH",
        "ledger",
        0,
        "ver1",
        "fp1",
        t0,
        t1,
        1,
        0,
        0,
        "OK",
        None,
        None,
    )
    assert ReplayService().replay(r, "ver1") == "run-a"


def test_replay_rejects_mismatch() -> None:
    t0, t1 = now_utc(), now_utc()
    r = RunRecord(
        "run-b",
        "BATCH",
        "ledger",
        0,
        "v2",
        "fp1",
        t0,
        t1,
        0,
        0,
        0,
        "OK",
        None,
        None,
    )
    with pytest.raises(MissingRuleSetVersionError):
        ReplayService().replay(r, "v1")


def test_run_record_frozen_shape() -> None:
    t0, t1 = now_utc(), now_utc()
    r = RunRecord(
        "r",
        "BATCH",
        "t",
        1,
        "v",
        "c",
        t0,
        t1,
        0,
        0,
        0,
        "OK",
        None,
        None,
    )
    assert r.replay_source_run_id is None
