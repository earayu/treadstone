#!/usr/bin/env bash
set -euo pipefail

ENV="${1:-local}"

echo "=== Treadstone Down (ENV=$ENV) ==="
echo ""

make undeploy-env ENV="$ENV"

if [ "$ENV" = "local" ]; then
    echo ""
    echo "Deleting Kind cluster ..."
    kind delete cluster --name treadstone
fi

echo ""
echo "Down complete (ENV=$ENV)."
