from datetime import UTC, datetime

from sparkrules.store.sql_metadata import _overlaps


def test_overlaps_edge_false_branches() -> None:
    t0 = datetime(2020, 1, 1, tzinfo=UTC)
    t1 = datetime(2020, 2, 1, tzinfo=UTC)
    t2 = datetime(2020, 3, 1, tzinfo=UTC)
    assert _overlaps(t1, None, t0, None) is True
    assert _overlaps(t0, t1, t1, t2) is False
    assert _overlaps(t2, None, t0, t1) is False
