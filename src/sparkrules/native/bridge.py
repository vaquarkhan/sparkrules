"""Load ``sparkrules_native`` PyO3 extension if present (see Tier 1 spec)."""

from __future__ import annotations

import os
from typing import Any, Optional


class NativeUnavailableError(RuntimeError):
    """Raised when :class:`NativeRuleExecutor` is requested without a working wheel."""


def load_native() -> Optional[Any]:
    if os.getenv("SPARKRULES_NATIVE_DISABLE") == "1":
        return None
    try:
        import sparkrules_native as mod  # type: ignore[import-not-found]
    except ImportError:
        return None
    required = ("compile_rulepack", "score_rows", "native_version", "rulepack_hash")
    if not all(hasattr(mod, s) for s in required):
        return None
    return mod
