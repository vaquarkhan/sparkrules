"""Exceptions raised by rule expression evaluation (distinct from DRL parse errors)."""


class RulePackVersionError(ValueError):
    """``RulePack.deserialize`` rejects bytes produced by unsupported formats (Req 34)."""


class RuleEvaluationError(Exception):
    """Evaluating a DRL `when` expression failed in a way users should not see as a raw TypeError.

    Common case: a bind path (e.g. ``$t.amount``) resolved to None because the fact JSON
    is missing the bound object (e.g. no top-level ``t`` key), then a numeric comparison
    was evaluated.
    """

    __slots__ = ("code",)

    def __init__(self, message: str, *, code: str = "EVALUATION_ERROR") -> None:
        super().__init__(message)
        self.code = code
