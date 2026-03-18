#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="treadstone"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KIND_CONFIG="${SCRIPT_DIR}/../deploy/kind/kind-config.yaml"

check_prerequisites() {
    local missing=()
    for cmd in docker kind kubectl helm; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo "ERROR: Missing required tools: ${missing[*]}"
        echo ""
        echo "Install instructions:"
        echo "  docker  — https://docs.docker.com/get-docker/"
        echo "  kind    — brew install kind"
        echo "  kubectl — brew install kubectl"
        echo "  helm    — brew install helm"
        exit 1
    fi
    if ! docker info &>/dev/null; then
        echo "ERROR: Docker daemon is not running. Start Docker Desktop first."
        exit 1
    fi
}

create_cluster() {
    if kind get clusters 2>/dev/null | grep -qx "$CLUSTER_NAME"; then
        echo "Kind cluster '$CLUSTER_NAME' already exists."
        kubectl cluster-info --context "kind-$CLUSTER_NAME"
        return 0
    fi

    echo "Creating Kind cluster '$CLUSTER_NAME' ..."
    kind create cluster --config "$KIND_CONFIG"
    echo ""
    kubectl cluster-info --context "kind-$CLUSTER_NAME"
}

verify_cluster() {
    echo ""
    echo "Verifying cluster nodes ..."
    kubectl get nodes
    echo ""
    echo "Kind cluster '$CLUSTER_NAME' is ready."
}

main() {
    echo "=== Treadstone Kind Cluster Setup ==="
    echo ""
    check_prerequisites
    create_cluster
    verify_cluster
    echo ""
    echo "Next steps:"
    echo "  make deploy-all ENV=dev"
}

main "$@"
