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
EXPECTED_NETWORK_POLICY_DENYLIST = [
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "100.64.0.0/10",
    "169.254.0.0/16",
    "127.0.0.0/8",
]
EXPECTED_SANDBOX_POD_SECURITY_CONTEXT = {
    "seccompProfile": {"type": "RuntimeDefault"},
}
EXPECTED_SANDBOX_CONTAINER_SECURITY_CONTEXT = {
    "allowPrivilegeEscalation": False,
    "readOnlyRootFilesystem": False,
    "seccompProfile": {"type": "RuntimeDefault"},
    "capabilities": {
        "drop": ["ALL"],
        "add": ["CHOWN", "DAC_OVERRIDE", "FOWNER", "KILL", "SETUID", "SETGID"],
    },
}


def _load_values(name: str) -> dict:
    return yaml.safe_load((SANDBOX_RUNTIME_DIR / name).read_text())


def test_default_values_keep_direct_acs_disabled() -> None:
    values = _load_values("values.yaml")

    assert values["directAcsScheduling"]["enabled"] is False
    assert values["directAcsScheduling"]["units"] == EXPECTED_DIRECT_ACS_UNITS


def test_default_values_enable_shared_sandbox_network_policies() -> None:
    values = _load_values("values.yaml")

    network_policies = values["networkPolicies"]
    assert network_policies["enabled"] is True
    assert network_policies["sandboxPodSelector"] == {"treadstone-ai.dev/workload": "sandbox"}
    assert network_policies["ingress"]["allowFromApi"]["podSelector"] == {"treadstone-ai.dev/component": "api"}
    assert network_policies["egress"]["allowPublicInternet"]["enabled"] is True
    assert network_policies["egress"]["allowPublicInternet"]["exceptCidrs"] == EXPECTED_NETWORK_POLICY_DENYLIST


def test_default_values_define_compatible_sandbox_security_contexts() -> None:
    values = _load_values("values.yaml")

    assert values["sandboxPodSecurityContext"] == EXPECTED_SANDBOX_POD_SECURITY_CONTEXT
    assert values["sandboxContainerSecurityContext"] == EXPECTED_SANDBOX_CONTAINER_SECURITY_CONTEXT


def test_prod_values_enable_direct_acs_with_expected_unit_order() -> None:
    values = _load_values("values-prod.yaml")

    assert values["directAcsScheduling"]["enabled"] is True
    assert values["directAcsScheduling"]["units"] == EXPECTED_DIRECT_ACS_UNITS
