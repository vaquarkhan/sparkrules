"""Restricted unpickling for :class:`sparkrules.compiler.rulepack.RulePack`.

``pickle.loads`` on untrusted bytes is unsafe (arbitrary code execution).  RulePack
broadcast bytes are only safe when the producer is trusted; by default we only
decode ``GLOBAL`` opcode targets under ``sparkrules.*`` plus ``builtins.getattr``
(which :class:`enum.Enum` uses).

Set ``SPARKRULES_RULEPACK_UNSAFE_PICKLE=1`` only for emergency recovery of legacy
artifacts in a trusted environment.
"""

from __future__ import annotations

import builtins as _builtins
import importlib
import io
import os
import pickle
from typing import Any


def _restricted_find_class(module: str, name: str) -> Any:
    """Allow only sparkrules subpackages and Enum glue (``builtins.getattr``)."""
    if module == "builtins":
        if name != "getattr":
            raise pickle.UnpicklingError(
                f"unsafe builtins global in RulePack pickle: builtins.{name}"
            )
        return getattr(_builtins, name)

    if not module.startswith("sparkrules."):
        raise pickle.UnpicklingError(
            f"unsafe module in RulePack pickle: {module}.{name}",
        )

    mod = importlib.import_module(module)
    try:
        return getattr(mod, name)
    except AttributeError as e:
        raise pickle.UnpicklingError(f"missing RulePack pickle global {module}.{name}") from e


class _RestrictedRulePackUnpickler(pickle.Unpickler):
    """Unpickler with a tight ``find_class`` for RulePack payloads."""

    def find_class(self, module: str, name: str) -> Any:
        return _restricted_find_class(module, name)


def loads_rulepack_payload(payload: bytes) -> Any:
    """Unpickle *payload* bytes (after stripping SRRP envelope) using restrictions."""
    if os.getenv("SPARKRULES_RULEPACK_UNSAFE_PICKLE", "").lower() in (
        "1",
        "true",
        "yes",
    ):
        return pickle.loads(payload)  # noqa: S301
    return _RestrictedRulePackUnpickler(io.BytesIO(payload)).load()


__all__ = ["loads_rulepack_payload"]
