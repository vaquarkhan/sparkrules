import sys
from pathlib import Path

from hypothesis import HealthCheck, settings

# Allow `import hypo_settings` in tests/property/
sys.path.insert(0, str(Path(__file__).resolve().parent / "property"))

PROFILE = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[
        HealthCheck.too_slow,
        HealthCheck.function_scoped_fixture,
        HealthCheck.data_too_large,
    ],
)
