from __future__ import annotations

import hashlib
import pickle
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sre.compiler.batcher import RuleBatch, RuleBatcher
from sre.compiler.classifier import Strategy, StrategyClassifier
from sre.compiler.discrimination import DiscriminationNetwork
from sre.parser import parse
from sre.parser.ast import RuleAst


@dataclass
class CompiledRulePackage:
    rule_set_version: str
    batches: list[RuleBatch]
    discrimination_networks: dict[str, DiscriminationNetwork]
    strategy_by_rule_id: dict[str, Strategy]
    rule_asts_by_id: dict[str, RuleAst]
    metadata: dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> bytes:
        return pickle.dumps(self, protocol=4)

    @staticmethod
    def deserialize(data: bytes) -> CompiledRulePackage:
        o = pickle.loads(data)
        if not isinstance(o, CompiledRulePackage):
            raise TypeError("invalid package")
        return o


@dataclass
class RuleCompiler:
    classifier: StrategyClassifier = field(
        default_factory=StrategyClassifier
    )
    batcher: RuleBatcher = field(default_factory=RuleBatcher)

    def compile(self, rules: dict[str, str], *, run_id: str | None = None) -> CompiledRulePackage:  # noqa: E501
        rid = run_id or str(uuid4())
        by_id: dict[str, RuleAst] = {k: parse(v) for k, v in rules.items()}
        st: dict[str, Strategy] = {
            k: self.classifier.classify(rules[k]) for k in by_id
        }
        bch = self.batcher.batch(list(rules))
        dnets: dict[str, DiscriminationNetwork] = {
            "b0": DiscriminationNetwork.build(rules),
        }
        body = hashlib.sha256("".join(sorted(rules)).encode()).hexdigest()
        return CompiledRulePackage(
            rule_set_version=body,
            batches=bch,
            discrimination_networks=dnets,
            strategy_by_rule_id=st,
            rule_asts_by_id=by_id,
            metadata={"run_id": rid},
        )
