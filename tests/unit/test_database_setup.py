from pathlib import Path

import pytest
import yaml
from sqlalchemy.engine import make_url

from treadstone.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_database_default_uses_local_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TREADSTONE_DATABASE_URL", raising=False)
    url = make_url(Settings(_env_file=None).database_url)

    assert url.drivername == "postgresql+asyncpg"
    assert url.host == "localhost"
    assert url.database == "treadstone"
    assert not url.query


def test_integration_ci_uses_isolated_postgres_service() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())
    job = workflow["jobs"]["integration"]
    database = job["services"]["postgres"]
    url = make_url(job["env"]["TREADSTONE_DATABASE_URL"])

    assert database["image"] == "postgres:16"
    assert "pg_isready" in database["options"]
    assert database["ports"] == ["5432:5432"]
    assert url.host == "localhost"
    assert url.username == database["env"]["POSTGRES_USER"]
    assert url.password == database["env"]["POSTGRES_PASSWORD"]
    assert url.database == database["env"]["POSTGRES_DB"]
    for step in job["steps"]:
        assert "TREADSTONE_DATABASE_URL" not in step.get("env", {})


def test_kind_postgres_is_ephemeral_and_cluster_internal() -> None:
    manifests = list(yaml.safe_load_all((ROOT / "deploy/kind/postgres.yaml").read_text()))
    by_kind = {obj["kind"]: obj for obj in manifests}
    namespace = by_kind["Namespace"]["metadata"]["name"]
    service = by_kind["Service"]
    deployment = by_kind["Deployment"]
    pod = deployment["spec"]["template"]
    container = pod["spec"]["containers"][0]

    assert namespace == "treadstone-db"
    assert service["metadata"]["namespace"] == namespace
    assert deployment["metadata"]["namespace"] == namespace
    assert service["spec"].get("type", "ClusterIP") == "ClusterIP"
    assert service["spec"]["selector"] == pod["metadata"]["labels"]
    assert container["image"] == "postgres:16"
    assert container["readinessProbe"]["exec"]["command"][0] == "pg_isready"
    assert pod["spec"]["automountServiceAccountToken"] is False
    assert pod["spec"]["volumes"] == [{"name": "data", "emptyDir": {}}]


def test_k8s_e2e_provisions_database_before_application() -> None:
    workflow = yaml.safe_load((ROOT / ".github/workflows/k8s-e2e.yml").read_text())
    steps = workflow["jobs"]["k8s-e2e"]["steps"]
    scripts = "\n".join(step.get("run", "") for step in steps)
    deploy = next(step["run"] for step in steps if step["name"] == "Kind cluster, images, deploy")

    assert (
        "postgresql+asyncpg://treadstone:treadstone@postgres.treadstone-db.svc.cluster.local:5432/treadstone" in scripts
    )
    assert deploy.index("scripts/kind-setup.sh") < deploy.index("deploy/kind/postgres.yaml")
    assert deploy.index("deploy/kind/postgres.yaml") < deploy.index("rollout status deployment/postgres")
    assert deploy.index("rollout status deployment/postgres") < deploy.index(
        "make deploy-runtime deploy-api deploy-web"
    )
    env_script = next(step["run"] for step in steps if step["name"] == "Write .env.local")
    assert "${{ steps." not in env_script
