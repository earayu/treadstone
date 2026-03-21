#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="treadstone"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KIND_CONFIG="${SCRIPT_DIR}/../deploy/kind/kind-config.yaml"
INGRESS_NGINX_VERSION="v1.12.1"

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

install_ingress_nginx() {
    if kubectl get namespace ingress-nginx &>/dev/null && \
       kubectl get pods -n ingress-nginx -l app.kubernetes.io/component=controller --no-headers 2>/dev/null | grep -q Running; then
        echo "ingress-nginx controller already running, skipping install."
        return 0
    fi

    echo ""
    echo "Installing ingress-nginx controller (${INGRESS_NGINX_VERSION}) ..."
    kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-${INGRESS_NGINX_VERSION}/deploy/static/provider/kind/deploy.yaml"
    echo "Waiting for ingress-nginx to be ready (timeout 300s) ..."
    kubectl wait --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=300s
    echo "ingress-nginx is ready."
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
    install_ingress_nginx
    verify_cluster
    echo ""
    echo "Next steps:"
    echo "  make deploy-all ENV=local"
}

main "$@"
