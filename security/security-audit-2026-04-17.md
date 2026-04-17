# Treadstone Sandbox Security Audit

## Metadata
- Audit date: 2026-04-17
- Repo: `https://github.com/earayu/treadstone`
- Branch: `main`
- Commit: `71fecfd7e1a647f77c1b50de08e2640c348c45b5`
- Scope: sandbox isolation, cluster reachability, deploy hardening, image/runtime attack surface
- Runtime under test: sandbox based on `ghcr.io/agent-infra/sandbox:1.0.0.152`

## Executive Summary
The current sandbox posture is not in a “tight tenant isolation” state. I did not obtain Kubernetes secrets or pod listings during this pass, but I did confirm multiple materially exploitable attack surfaces:

1. The live sandbox can directly reach cluster-internal control surfaces that the chart intends to deny, including `kubernetes.default.svc`, a node kubelet on `:10250`, and internal ClusterIP services.
2. The sandbox runtime intentionally keeps a compatibility-first, root-capable main container with a writable root filesystem and without a `drop: [ALL]` capability policy.
3. The bundled browser is launched with `--no-sandbox`, `--disable-web-security`, and a live DevTools endpoint on `127.0.0.1:9222`, while additional localhost automation services are reachable without extra auth inside the pod.
4. The control-plane Deployment is reachable from the sandbox on its ClusterIP and uses a service account with cluster-scoped permissions; that becomes a high-value lateral target if any API bug or RCE exists.

The key root cause found during the cluster-side investigation is that the ACK/Terway stack is configured with network-policy enforcement disabled: `kube-system/eni-config` contains `disable_network_policy: "true"`. That explains why the rendered sandbox `NetworkPolicy` objects exist but are not acting as a real isolation boundary in production.

## Key Findings

### 1. High: private-cluster egress controls are not effective in the live environment
- Intended by chart:
  - `deploy/sandbox-runtime/values.yaml`
  - `deploy/sandbox-runtime/templates/networkpolicy.yaml`
  - `deploy/sandbox-runtime/README.md`
- Observed from the live sandbox:
  - `https://kubernetes.default.svc/version` returned `200`
  - `https://kubernetes.default.svc/livez` and `/readyz` returned `200`
  - `https://kubernetes.default.svc/api` and `/apis` returned `403 system:anonymous`
  - internal Treadstone ClusterIP services were reachable
  - node kubelet `:10250` was reachable and answered `401`
- Confirmed root cause from cluster side:
  - `kube-system/eni-config` sets `disable_network_policy: "true"`

### 2. High: main sandbox container is intentionally root-compatible and not “restricted”
- Evidence:
  - `deploy/sandbox-runtime/templates/sandbox-templates.yaml`
  - `deploy/sandbox-runtime/values.yaml`
  - `deploy/sandbox-runtime/README.md`
  - `treadstone/infra/services/k8s_client.py`
- Current baseline:
  - no `runAsNonRoot`
  - no main-container `capabilities.drop: [ALL]`
  - writable root filesystem
  - real pod observed as `uid=0(root)`

### 3. High: browser isolation inside the sandbox is deliberately weakened
- Runtime evidence:
  - Chromium launched with `--no-sandbox`
  - `--disable-web-security`
  - `--remote-debugging-port=9222`
  - `127.0.0.1:9222/json/version` and `/json/list` were readable
  - localhost code-server / Jupyter / helper APIs were reachable inside the sandbox

### 4. Medium: service-link environment leakage makes cluster discovery easier
- Claim-template path omitted `enableServiceLinks: false` and a dedicated sandbox SA:
  - `deploy/sandbox-runtime/templates/sandbox-templates.yaml`
- Direct Sandbox CR path also omitted them:
  - `treadstone/infra/services/k8s_client.py`
- Runtime impact:
  - sandbox environment exposed `KUBERNETES_SERVICE_HOST=192.168.0.1`
  - internal Treadstone service IPs were also injected as env vars

### 5. Medium: control plane is a reachable, high-value lateral target
- Evidence:
  - `deploy/treadstone/templates/deployment.yaml`
  - `deploy/treadstone/templates/clusterrole.yaml`
- The internal API ClusterIP was reachable from the sandbox.
- This pass did not find an auth bypass, but any future control-plane RCE/SSRF/privilege bug would land on a service with meaningful cluster permissions.

## What Was Not Confirmed
- No Kubernetes secret values were recovered in this pass.
- No authenticated pod listing was obtained from kube-apiserver or kubelet.
- Cloud metadata `169.254.169.254` did not answer from this sandbox.

## Immediate Fixes
1. Re-enable actual NetworkPolicy enforcement in the cluster.
2. Re-test from inside a live sandbox:
   - `192.168.0.1:443`
   - node kubelet `:10250`
   - internal Treadstone ClusterIP services
3. Set `enableServiceLinks: false` on sandbox pods.
4. Use a dedicated zero-permission sandbox service account instead of `default`.

## Medium-Term Fixes
1. Replace the upstream opaque sandbox image with a rootless-compatible custom image.
2. Tighten to `runAsNonRoot` and main-container `capabilities.drop: [ALL]` once the target runtime supports it.
3. Keep “sandbox can reach kube-apiserver / kubelet / internal services” as a security regression test.

## Launch Readiness
- For hostile multi-tenant sandbox claims: not ready.
- For convenience sandboxes where users are effectively trusted and strong isolation is not promised: the current setup is understandable, but the security claim must stay conservative.
