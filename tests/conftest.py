import os
import sys
from pathlib import Path

from hypothesis import HealthCheck, settings

# Tests historically assumed implicit platform_admin without headers; production
# defaults to zero roles unless SPARKRULES_DEV_ALLOW_DEFAULT_SUPERUSER is set.
os.environ.setdefault("SPARKRULES_DEV_ALLOW_DEFAULT_SUPERUSER", "true")

# Isolate from the developer shell: Workbench auth gates the whole API (401) if set.
for _k in (
    "SPARKRULES_WORKBENCH_AUTH",
    "SPARKRULES_DISABLE_WORKBENCH_GATE",
    "SPARKRULES_WORKBENCH_DEFAULT_CREDENTIALS",
    "SPARKRULES_WORKBENCH_PASSWORD",
    "SPARKRULES_WORKBENCH_USER",
    "SPARKRULES_WORKBENCH_SECRET",
):
    os.environ.pop(_k, None)

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
