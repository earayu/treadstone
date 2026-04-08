from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SANDBOX_RUNTIME_DIR = REPO_ROOT / "deploy" / "sandbox-runtime"
EXPECTED_DIRECT_ACS_UNITS = [
    {"resource": "ecs"},
    {
        "resource": "acs",
        "podLabels": {
            "alibabacloud.com/compute-class": "general-purpose",
            "alibabacloud.com/compute-qos": "default",
        },
    },
    {
        "resource": "acs",
        "podLabels": {
            "alibabacloud.com/compute-class": "performance",
            "alibabacloud.com/compute-qos": "default",
        },
    },
    {
        "resource": "acs",
        "podLabels": {
            "alibabacloud.com/compute-class": "general-purpose",
            "alibabacloud.com/compute-qos": "best-effort",
        },
    },
    {
        "resource": "acs",
        "podLabels": {
            "alibabacloud.com/compute-class": "performance",
            "alibabacloud.com/compute-qos": "best-effort",
        },
    },
]


def _load_values(name: str) -> dict:
    return yaml.safe_load((SANDBOX_RUNTIME_DIR / name).read_text())


def test_default_values_keep_direct_acs_disabled() -> None:
    values = _load_values("values.yaml")

    assert values["directAcsScheduling"]["enabled"] is False
    assert values["directAcsScheduling"]["units"] == EXPECTED_DIRECT_ACS_UNITS


def test_prod_values_enable_direct_acs_with_expected_unit_order() -> None:
    values = _load_values("values-prod.yaml")

    assert values["directAcsScheduling"]["enabled"] is True
    assert values["directAcsScheduling"]["units"] == EXPECTED_DIRECT_ACS_UNITS
