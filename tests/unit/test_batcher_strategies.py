from sparkrules.compiler.batcher import RuleBatcher
from sparkrules.compiler.classifier import Strategy


def test_batcher_partitions_by_strategy_before_batch_size() -> None:
    b = RuleBatcher(50)
    st = {"a": Strategy.BROADCAST, "b": Strategy.SQL_JOIN, "c": Strategy.DATAFRAME}
    batches = b.batch(["a", "b", "c"], st)
    assert [batch.strategy for batch in batches] == ["BROADCAST", "SQL_JOIN", "DATAFRAME"]
    flat = [rid for batch in batches for rid in batch.rule_ids]
    assert flat == ["a", "b", "c"]


def test_batcher_empty_list_with_strategy_map() -> None:
    b = RuleBatcher(5)
    assert b.batch([], {"a": Strategy.BROADCAST}) == []
