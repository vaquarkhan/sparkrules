"""Native (Rust) optional accelerator — local/driver scoring only."""

from __future__ import annotations

from sparkrules.native.bridge import NativeUnavailableError, load_native
from sparkrules.native.executor import NativeRuleExecutor

__all__ = [
    "load_native",
    "NativeUnavailableError",
    "NativeRuleExecutor",
]
