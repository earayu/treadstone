# agent-sandbox Helm Chart

Thin Helm wrapper around the upstream [kubernetes-sigs/agent-sandbox](https://github.com/kubernetes-sigs/agent-sandbox) controller.

## Vendor Patch

The upstream release provides two files meant to be applied sequentially:

```bash
kubectl apply -f manifest.yaml    # core install
kubectl apply -f extensions.yaml  # add extensions (updates the Deployment)
```

`kubectl apply` is idempotent — the second command updates the existing Deployment
by adding the `--extensions` flag. Helm's fresh install cannot do this; it tries to
**create** both Deployments and fails with `already exists`.

**What we changed:**

- `upstream/manifest.yaml` — added `--extensions` to the controller Deployment args
- `upstream/extensions.yaml` — removed the duplicate Deployment block (only the
  Deployment was duplicated; all CRDs and RBAC are unique and unchanged)

The end result is identical to applying both files sequentially with `kubectl apply`.

## Upgrading Upstream Version

When a new upstream version is released:

1. Download the new `manifest.yaml` and `extensions.yaml` from the release page and
   overwrite the files in `upstream/`.
2. Diff the new `extensions.yaml` Deployment against the new `manifest.yaml` Deployment.
3. Merge any new args/fields from the `extensions.yaml` Deployment into `manifest.yaml`.
4. Remove the Deployment block from `extensions.yaml`.
5. Re-add the `# VENDOR PATCH` comments so the next person knows why.

A better long-term fix is to upgrade to Helm ≥ 3.13 and add `--server-side` to the
`deploy-infra` Makefile target, which lets Helm use server-side apply semantics and
handles the update naturally — no vendor modification required.
