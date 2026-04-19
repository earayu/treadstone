# sandbox-runtime Helm chart

Deploys `SandboxTemplate` and optional `SandboxWarmPool` CRs for the agent-sandbox controller.

## Provisioning paths vs `init-home`

Treadstone uses two sandbox provisioning paths:

1. **SandboxClaim + SandboxTemplate (this chart)** — Ephemeral sandboxes from Helm-defined templates. Pods have **no PVC** and **no init container** in the template.
2. **Direct `Sandbox` CR from the API** (`treadstone/services/k8s_client.py`) — Used when persistent storage is requested. The API adds `volumeClaimTemplates` and an `**init-home` init container** only in this path.

The init container exists because mounting a PVC at `/home/gem` **hides the image’s home directory**; the init seeds the volume from the image's explicit home template on first boot. It is **not** used by Claim-only workloads.

Security contexts for the main container are defined in `values.yaml` (`sandboxPodSecurityContext`, `sandboxContainerSecurityContext`). The direct path mirrors the same baseline in code; keep them aligned when changing defaults.

## Shared NetworkPolicy model

This chart can also render shared Kubernetes `NetworkPolicy` objects for all sandbox pods.

- Coverage: both **claim** pods from `SandboxTemplate` and **direct** pods from API-created `Sandbox` CRs
- Ownership: Helm-only; no per-sandbox lifecycle management in Python
- Pod match: `networkPolicies.sandboxPodSelector` (defaults to `treadstone-ai.dev/workload=sandbox`)

The default V1 policy set is intentionally compatibility-first:

- `sandbox-default-deny`: selects sandbox pods and isolates both ingress and egress
- `sandbox-allow-from-api`: allows only Treadstone API pods to reach sandbox `TCP/8080`
- `sandbox-allow-dns`: allows DNS to `kube-system`
- `sandbox-allow-public-egress`: allows public egress while excluding `exceptCidrs`
- sandbox templates pin `enableServiceLinks: false` and a dedicated zero-permission service account (`treadstone-sandbox`) to reduce in-pod cluster discovery

`exceptCidrs` starts with common private and cluster-internal ranges, but it is only a starting point. Override it in `values-local.yaml`, `values-demo.yaml`, or `values-prod.yaml` with the real Pod/Service/VPC networks for that environment.

This is a practical V1 control, not a final hard-isolation model:

- public internet access stays enabled by default for AIO sandbox compatibility
- cluster-internal reachability is reduced through the denylist, not fully auto-discovered
- future tightening can move to `80/443`-only defaults or plan-specific exceptions without changing sandbox lifecycle code

## Sandbox Security Context Baseline

The maintained runtime image (`ghcr.io/earayu/treadstone-sandbox`, built on `ghcr.io/agent-infra/sandbox`) now treats **rootless startup as part of the image contract**. The image creates the `gem` user/group at build time, prepares `/home/gem`, and keeps the runtime bootstrap out of the container's root path.

The default Treadstone baseline is therefore **rootless-first hardening**:

- keep `automountServiceAccountToken: false`
- set `enableServiceLinks: false`
- use a dedicated sandbox service account with no RBAC bindings
- keep `allowPrivilegeEscalation: false`
- set `runAsNonRoot: true`
- set `runAsUser: 1000` / `runAsGroup: 1000`
- keep `seccompProfile: RuntimeDefault`
- keep `readOnlyRootFilesystem: false`
- do not force any `capabilities` override on either container, because some ACS/ECI policies reject that stanza outright

The remaining boundary is deliberate:

- the direct-path `init-home` init container remains non-root
- direct sandboxes still use `fsGroup` for the PVC-backed `/home/gem` workspace
- `init-home` seeds from a read-only home template instead of depending on the main container's runtime bootstrap
- ACS/ECI scheduling remains compatible because the Pod spec does not request disallowed capability overrides
- this baseline is **not** Pod Security Standards `restricted` compliance

Workspace PVCs rely on **fsGroup** for permissions; confirm your **StorageClass / CSI** supports `fsGroup` behavior for production.
