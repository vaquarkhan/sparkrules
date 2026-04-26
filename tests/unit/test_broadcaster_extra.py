from sre.transport.broadcaster import RuleBroadcaster, rule_broadcast


def test_chunk_empty_payload() -> None:
    assert len(RuleBroadcaster(10).chunk(b"")) == 1


def test_rule_broadcast_bytes() -> None:
    b = rule_broadcast({"a": 1})
    assert isinstance(b, bytes) and len(b) > 0
