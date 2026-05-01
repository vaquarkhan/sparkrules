from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from sparkrules.sim import RuleSimulator
from sparkrules.store import InMemoryRuleMetadataStore


@dataclass
class ConnectServer:
    store: InMemoryRuleMetadataStore = field(default_factory=InMemoryRuleMetadataStore)
    sim: RuleSimulator = field(default_factory=RuleSimulator)
    _handlers: dict[str, Callable[..., Any]] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        self._handlers["list_rules"] = self._h_list
        self._handlers["parse"] = self._h_parse

    def _h_list(self) -> list[str]:  # noqa: C901, E501
        return [r.rule_handle for r in self.store.list(None)]

    def _h_parse(self, s: str) -> str:
        from sparkrules.parser import parse

        a = parse(s)
        return a.name

    def dispatch(self, name: str, *args: Any, **kwargs: Any) -> Any:
        f = self._handlers.get(name)
        if f is None:
            raise KeyError(name)
        return f(*args, **kwargs)
