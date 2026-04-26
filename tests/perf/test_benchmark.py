import pytest


@pytest.mark.perf
def test_smoke_benchmark() -> None:
    assert 1 + 1 == 2
