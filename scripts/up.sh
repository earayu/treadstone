#!/usr/bin/env bash
set -euo pipefail

ENV="${1:-local}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLUSTER_NAME="treadstone"

echo "=== Treadstone Up (ENV=$ENV) ==="
echo ""

if [ "$ENV" = "local" ]; then
    bash "$SCRIPT_DIR/kind-setup.sh"
    echo ""
    echo "Building Docker image ..."
    docker build -t treadstone:latest .
    echo ""
    echo "Loading image into Kind cluster ..."
    kind load docker-image treadstone:latest --name "$CLUSTER_NAME"
fi

echo ""
echo "Deploying Helm charts (ENV=$ENV) ..."
make deploy-all ENV="$ENV"

echo ""
echo "Up complete (ENV=$ENV)."
if [ "$ENV" = "local" ]; then
    echo "Verify with: kubectl get pods -n treadstone"
fi
