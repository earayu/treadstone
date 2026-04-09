#!/usr/bin/env bash
set -euo pipefail

ENV="${1:-local}"
CLUSTER_PROFILE="${2:-${CLUSTER_PROFILE:-}}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLUSTER_NAME="treadstone"

echo "=== Treadstone Up (ENV=$ENV) ==="
echo ""

if [ "$ENV" = "local" ]; then
    bash "$SCRIPT_DIR/kind-setup.sh"
    echo ""
    echo "Building API Docker image ..."
    make image-api
    echo ""
    echo "Loading API image into Kind cluster ..."
    kind load docker-image treadstone:latest --name "$CLUSTER_NAME"
    echo ""
    echo "Building web Docker image ..."
    make image-web
    echo ""
    echo "Loading web image into Kind cluster ..."
    kind load docker-image treadstone-web:latest --name "$CLUSTER_NAME"
fi

echo ""
echo "Verifying kubectl context ..."
if [ "$ENV" = "prod" ]; then
	bash "$SCRIPT_DIR/check-k8s-context.sh" prod
else
	bash "$SCRIPT_DIR/check-k8s-context.sh" local
fi

echo ""
echo "Deploying Helm charts (ENV=$ENV) ..."
if [ -n "$CLUSTER_PROFILE" ]; then
    make deploy-all ENV="$ENV" CLUSTER_PROFILE="$CLUSTER_PROFILE"
else
    make deploy-all ENV="$ENV"
fi

NS="treadstone-${ENV}"

echo ""
echo "Up complete (ENV=$ENV)."
if [ "$ENV" = "local" ]; then
    echo "Verify with: kubectl --context kind-${CLUSTER_NAME} get pods -n $NS"
fi
