"""SparkRules engine (reference Python implementation)."""

__version__ = "1.1.0"


def _check_api_extras() -> None:
    """Provide a clear error when sparkrules[api] extras are not installed."""
    pass  # Core imports work without extras; API imports fail with clear ImportError
