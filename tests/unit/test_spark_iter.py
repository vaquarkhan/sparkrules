"""Pure-Python tests for sre.spark (no JVM)."""

from sre.spark import iter_rule_rows

_DRL = """
rule r1
when
$z : T ( $z.n == 1 )
then
result.x = 1;
end
"""


def test_iter_rule_rows_dict_rows() -> None:
    t = list(
        iter_rule_rows(
            iter(
                [
                    {"id": "1", "z": {"n": 1}},
                    {"id": "2", "z": {"n": 0}},
                ],
            ),
            _DRL,
        )
    )
    assert t[0][0] == "1" and t[0][1] is True
    assert t[1][1] is False
