# sandbox-runtime Helm chart

Deploys `SandboxTemplate` and optional `SandboxWarmPool` CRs for the agent-sandbox controller.

## Provisioning paths vs `init-home`

Treadstone uses two sandbox provisioning paths:

1. **SandboxClaim + SandboxTemplate (this chart)** — Ephemeral sandboxes from Helm-defined templates. Pods have **no PVC** and **no init container** in the template.
2. **Direct `Sandbox` CR from the API** (`treadstone/services/k8s_client.py`) — Used when persistent storage is requested. The API adds `volumeClaimTemplates` and an `**init-home` init container** only in this path.

The init container exists because mounting a PVC at `/home/gem` **hides the image’s home directory**; the init seeds the volume from the image layer (mounted at a separate path) on first boot. It is **not** used by Claim-only workloads.

Security contexts for the main container are defined in `values.yaml` (`sandboxPodSecurityContext`, `sandboxContainerSecurityContext`). The direct path mirrors the same baseline in code; keep them aligned when changing defaults.

## Pod Security Standards (PSS)

Defaults are **less strict** on purpose: `readOnlyRootFilesystem` is **false** so the stock sandbox image can write where it expects (e.g. under `/tmp`). That is closer to the **baseline** profile than to **restricted** (which requires a read-only root filesystem and writable paths only through declared volumes). Namespaces that **enforce restricted** may reject these Pods unless you tighten the image/volumes first and set `readOnlyRootFilesystem: true` (and related overrides) in values.

Workspace PVCs rely on **fsGroup** for permissions; confirm your **StorageClass / CSI** supports `fsGroup` behavior for production.