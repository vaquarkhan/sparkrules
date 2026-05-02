from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


class ChainingLimitExceededError(ValueError):
    pass


def order_activations(
    activations: Sequence[tuple[int, str, str | None, str]],
) -> list[str]:
    """Order activations per Req 24 / Req 17: (-salience, rule handle ascending, declaration order ascending)."""

    indexed = list(enumerate(activations))
    indexed.sort(key=lambda ix: (-ix[1][0], ix[1][3], ix[0]))
    return [ix[1][3] for ix in indexed]


def resolve_activation_groups(fired: Sequence[tuple[str, str | None]]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for h, g in fired:
        if g and g in seen:
            continue
        if g:
            seen.add(g)
        out.append(h)
    return out


def forward_chain(
    start: str,
    steps: dict[str, list[str]],
    *,
    max_depth: int = 100,
) -> list[str]:
    out: list[str] = [start]
    d = 0
    while d < max_depth and out[-1] in steps:
        nxt = steps[out[-1]]
        if not nxt:
            break
        out.append(nxt[0])
        d += 1
    if d >= max_depth:
        raise ChainingLimitExceededError()
    return out


@dataclass
class AgendaController:
    def order_activations(self, acts: Sequence[tuple[int, str, str | None, str]]) -> list[str]:
        return order_activations(acts)
