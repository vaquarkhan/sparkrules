from pathlib import Path

import pytest
import yaml


def _k8s_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "deploy" / "k8s"


@pytest.mark.parametrize(
    "name",
    [
        "namespace.yaml",
        "configmap.yaml",
        "rule-api.yaml",
        "connect.yaml",
        "values-dev.yaml",
    ],
)
def test_yaml_parses(name: str) -> None:
    p = _k8s_dir() / name
    assert p.is_file()
    with p.open(encoding="utf-8") as f:
        list(yaml.safe_load_all(f))
