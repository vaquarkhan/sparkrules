class UnknownCatalystRuleError(KeyError):
    pass


class CatalystConfigurer:
    def __init__(self) -> None:
        self.rules: dict[str, bool] = dict(KNOWN_CATALYST_RULES)


KNOWN_CATALYST_RULES: dict[str, bool] = {
    "fusion_enabled": True,
    "adaptive": True,
}
