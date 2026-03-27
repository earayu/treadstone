#!/usr/bin/env bash
set -euo pipefail

CLUSTER_NAME="treadstone"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
KIND_CONFIG="${SCRIPT_DIR}/../deploy/kind/kind-config.yaml"

# Pin ALL image tags so upgrades are explicit and reproducible.
# When bumping INGRESS_NGINX_VERSION, check the deploy.yaml for the
# matching kube-webhook-certgen tag and update WEBHOOK_CERTGEN_TAG.
INGRESS_NGINX_VERSION="v1.12.1"
WEBHOOK_CERTGEN_TAG="v1.5.2"
LOCAL_PATH_PROVISIONER_VERSION="v0.0.31"

INFRA_IMAGES=(
    "registry.k8s.io/ingress-nginx/controller:${INGRESS_NGINX_VERSION}"
    "registry.k8s.io/ingress-nginx/kube-webhook-certgen:${WEBHOOK_CERTGEN_TAG}"
    "rancher/local-path-provisioner:${LOCAL_PATH_PROVISIONER_VERSION}"
)

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
    # Strip proxy env vars: Kind propagates them into node containers where
    # 127.0.0.1 points to the container itself, not the host — causing all
    # in-cluster image pulls to fail with "proxyconnect: connection refused".
    env -u http_proxy -u https_proxy -u HTTP_PROXY -u HTTPS_PROXY \
        kind create cluster --config "$KIND_CONFIG"
    echo ""
    kubectl cluster-info --context "kind-$CLUSTER_NAME"
}

preload_infra_images() {
    echo ""
    echo "Pre-pulling infrastructure images on host ..."
    for img in "${INFRA_IMAGES[@]}"; do
        if docker image inspect "$img" &>/dev/null; then
            echo "  $img (cached)"
        else
            echo "  Pulling $img ..."
            docker pull "$img"
        fi
    done

    echo "Loading infrastructure images into Kind cluster ..."
    kind load docker-image "${INFRA_IMAGES[@]}" --name "$CLUSTER_NAME"
    echo "Infrastructure images preloaded."
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

install_local_path_provisioner() {
    if kubectl get namespace local-path-storage &>/dev/null && \
       kubectl get deployment -n local-path-storage local-path-provisioner &>/dev/null; then
        echo ""
        echo "local-path-provisioner already running, skipping install."
        return 0
    fi

    echo ""
    echo "Installing local-path-provisioner (${LOCAL_PATH_PROVISIONER_VERSION}) ..."
    kubectl apply -f "https://raw.githubusercontent.com/rancher/local-path-provisioner/${LOCAL_PATH_PROVISIONER_VERSION}/deploy/local-path-storage.yaml"
    echo "Waiting for local-path-provisioner to be ready (timeout 300s) ..."
    kubectl wait --namespace local-path-storage \
        --for=condition=available deployment/local-path-provisioner \
        --timeout=300s
    echo "local-path-provisioner is ready."
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
    preload_infra_images
    install_ingress_nginx
    install_local_path_provisioner
    verify_cluster
    echo ""
    echo "Next steps:"
    echo "  make deploy-all ENV=local"
}

main "$@"
