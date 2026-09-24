# agent-sandbox Helm Chart

Thin Helm wrapper around the upstream [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) controller.

## Vendor Patch

The upstream release provides a core controller manifest and a separate
extensions controller manifest meant to be applied sequentially:

```bash
kubectl apply -f k8s/controller.yaml
kubectl apply -f k8s/extensions.controller.yaml
```

The second apply updates the existing Deployment by adding the `--extensions`
flag. This chart renders one equivalent Deployment so a fresh Helm install
does not create the same object twice.

**What we changed:**

- `upstream/manifest.yaml` — assembled the v1.0.3 core controller resources,
  core CRD, and core RBAC; the upstream Deployment is rendered by Helm
- `upstream/extensions.yaml` — assembled the v1.0.3 extension CRDs and RBAC;
  the duplicate Deployment block is omitted
- `templates/controller-deployment.yaml` — one controller Deployment with
  `--extensions`, configurable image, replicas, and resources

The rendered result preserves the upstream controller behavior while allowing
environment-specific image and replica/resource values.

## Breaking Upgrade From v0.3.x

This chart intentionally serves only the upstream `v1beta1` APIs. It does not
preserve or convert Treadstone's former `v1alpha1` Sandbox, SandboxClaim,
SandboxTemplate, or SandboxWarmPool resources.

For a disposable Treadstone cluster, remove the old Treadstone sandbox
resources and release before installing this chart again:

```bash
helm uninstall sandbox-runtime-<env> -n treadstone-<env> || true
kubectl delete sandboxclaims,sandboxes -n treadstone-<env> --all
helm uninstall agent-sandbox || true
kubectl delete crd \
  sandboxclaims.extensions.agents.x-k8s.io \
  sandboxtemplates.extensions.agents.x-k8s.io \
  sandboxwarmpools.extensions.agents.x-k8s.io \
  sandboxes.agents.x-k8s.io
make deploy-infra ENV=<env>
make deploy-runtime ENV=<env>
```

Do not run this procedure on a shared cluster: deleting the CRDs deletes
resources for every namespace served by this controller.

## Upgrading Upstream Version

When a new upstream version is released:

1. Download the new upstream release archive.
2. Assemble the core controller, core CRD, and core RBAC into `upstream/manifest.yaml`.
3. Assemble the extension CRDs and extension RBAC into `upstream/extensions.yaml`.
4. Merge any new Deployment args or fields from the extension controller into
   the single Deployment in `templates/controller-deployment.yaml`.
5. Keep the controller image tag and resource defaults in all `values*.yaml`
   files aligned with the vendored release.
