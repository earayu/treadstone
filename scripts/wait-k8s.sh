#!/usr/bin/env bash
# Wait for Kind + Treadstone local stack readiness (ingress, storage, controller, workloads).
#
# Usage:
#   bash scripts/wait-k8s.sh [ENV]
# ENV defaults to "local" (namespace treadstone-local).

set -euo pipefail

ENV="${1:-local}"
NS="treadstone-${ENV}"
AGENT_NS="${AGENT_NS:-agent-sandbox-system}"
INGRESS_NS="${INGRESS_NS:-ingress-nginx}"
LOCAL_PATH_NS="${LOCAL_PATH_NS:-local-path-storage}"
TIMEOUT_ROLLOUT="${TIMEOUT_ROLLOUT:-600s}"
TIMEOUT_JOB="${TIMEOUT_JOB:-300s}"

echo "=== wait-k8s (ENV=$ENV, NS=$NS) ==="

echo "Waiting for ingress-nginx controller ..."
kubectl wait --namespace "$INGRESS_NS" \
	--for=condition=ready pod \
	--selector=app.kubernetes.io/component=controller \
	--timeout="$TIMEOUT_ROLLOUT"

echo "Waiting for local-path-provisioner ..."
kubectl wait --namespace "$LOCAL_PATH_NS" \
	--for=condition=available deployment/local-path-provisioner \
	--timeout="$TIMEOUT_ROLLOUT"

echo "Waiting for agent-sandbox controller ..."
kubectl rollout status deployment/agent-sandbox-controller -n "$AGENT_NS" --timeout="$TIMEOUT_ROLLOUT"

API_RELEASE="treadstone-${ENV}"
WEB_RELEASE="treadstone-web-${ENV}"
API_DEPLOY="${API_RELEASE}-treadstone"
WEB_DEPLOY="${WEB_RELEASE}-treadstone-web"

MIG_JOB="${API_DEPLOY}-migrate"
if kubectl get job "$MIG_JOB" -n "$NS" &>/dev/null; then
	echo "Waiting for migration job ${MIG_JOB} ..."
	if kubectl wait --for=condition=complete "job/${MIG_JOB}" -n "$NS" --timeout="$TIMEOUT_JOB" 2>/dev/null; then
		echo "Migration job succeeded."
	else
		echo "ERROR: migration job failed or timed out." >&2
		kubectl logs -n "$NS" "job/${MIG_JOB}" --all-containers=true --tail=200 || true
		exit 1
	fi
else
	echo "No active migration job (already cleaned up or not created yet)."
fi

echo "Waiting for API deployment ..."
kubectl rollout status "deployment/${API_DEPLOY}" -n "$NS" --timeout="$TIMEOUT_ROLLOUT"

echo "Waiting for Web deployment ..."
kubectl rollout status "deployment/${WEB_DEPLOY}" -n "$NS" --timeout="$TIMEOUT_ROLLOUT"

# Warm pool for aio-sandbox-tiny (values-local): pool name is "<template>-pool"
POOL_NAME="${SANDBOX_WARM_POOL_NAME:-aio-sandbox-tiny-pool}"
echo "Waiting for SandboxWarmPool ${POOL_NAME} (best-effort, up to ~10 min) ..."
if kubectl get sandboxwarmpool "$POOL_NAME" -n "$NS" &>/dev/null; then
	for i in $(seq 1 120); do
		ready=$(kubectl get sandboxwarmpool "$POOL_NAME" -n "$NS" -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "")
		want=$(kubectl get sandboxwarmpool "$POOL_NAME" -n "$NS" -o jsonpath='{.spec.replicas}' 2>/dev/null || echo "1")
		if [[ "$ready" =~ ^[0-9]+$ && "$want" =~ ^[0-9]+$ && "$ready" -ge "$want" ]]; then
			echo "SandboxWarmPool ${POOL_NAME} ready (${ready}/${want})."
			break
		fi
		echo "  warm pool readyReplicas=${ready:-0}, want=${want} ..."
		if [ "$i" -eq 120 ]; then
			echo "::warning:: SandboxWarmPool ${POOL_NAME} not fully ready in time; continuing."
		fi
		sleep 5
	done
else
	echo "No SandboxWarmPool ${POOL_NAME} — skipping warm pool wait."
fi

echo "=== wait-k8s: done ==="
