import os
import sys
from pathlib import Path

from hypothesis import HealthCheck, settings

# Tests historically assumed implicit platform_admin without headers; production
# defaults to zero roles unless SPARKRULES_DEV_ALLOW_DEFAULT_SUPERUSER is set.
os.environ.setdefault("SPARKRULES_DEV_ALLOW_DEFAULT_SUPERUSER", "true")

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
