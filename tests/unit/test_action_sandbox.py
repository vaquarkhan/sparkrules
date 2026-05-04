from __future__ import annotations

import pytest

from sparkrules.compliance.action_sandbox import validate_python_literal_expression


def test_validate_literal_accepts_simple_math() -> None:
    validate_python_literal_expression("1 + 2 * 3")


def test_validate_literal_rejects_call() -> None:
    with pytest.raises(ValueError, match="Call"):
        validate_python_literal_expression("__import__('os')")
