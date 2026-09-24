#!/usr/bin/env bash
# Verify an existing image; never build or commit a container's test mutations.
set -euo pipefail

IMAGE="${1:?Usage: verify-sandbox-image.sh IMAGE [OUTPUT_DIR]}"
OUTPUT_DIR="${2:-reports/sandbox-image}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"
IMAGE_ID="$(docker image inspect --format '{{.Id}}' "$IMAGE")"
NAME="sandbox-verify-${GITHUB_RUN_ID:-local}-$$"
VOLUME="${NAME}-home"
docker image inspect "$IMAGE" >"$OUTPUT_DIR/image.json"
docker volume create "$VOLUME" >/dev/null

cleanup() {
  local status=$?
  trap - EXIT
  docker logs "$NAME" >"$OUTPUT_DIR/container.log" 2>&1 || true
  docker cp "$NAME:/tmp/workspace-validation/." "$OUTPUT_DIR/" 2>/dev/null || true
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker volume rm "$VOLUME" >/dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT

start() {
  docker run -d --name "$NAME" --security-opt no-new-privileges \
    --shm-size=512m --mount "type=volume,src=$VOLUME,dst=/home/gem" "$IMAGE_ID"
  for script in test_sandbox_image.py test_sandbox_persistence.py test_sandbox_workspace.py sandbox_openapi_base.json; do
    docker cp "$ROOT/scripts/$script" "$NAME:/tmp/$script"
  done
}

start
docker exec "$NAME" python /tmp/test_sandbox_image.py
docker exec "$NAME" python /tmp/test_sandbox_persistence.py seed
docker restart --time 30 "$NAME"
docker exec "$NAME" python /tmp/test_sandbox_persistence.py check
docker exec "$NAME" python /tmp/test_sandbox_image.py

# A replacement container with the same home volume is closer to a PVC resume
# than restarting the original container and retaining its writable layer.
docker stop --time 30 "$NAME"
docker rm "$NAME"
start
docker exec "$NAME" python /tmp/test_sandbox_persistence.py check
docker exec "$NAME" python /tmp/test_sandbox_image.py
docker exec "$NAME" sh -c 'python -m pip freeze; claude --version; codex --version; kimi --version; cursor-agent --version' \
  >"$OUTPUT_DIR/tools.txt"
docker exec --user root "$NAME" pip install playwright==1.55.0
docker exec "$NAME" python /tmp/test_sandbox_workspace.py
test "$(docker image inspect --format '{{.Id}}' "$IMAGE")" = "$IMAGE_ID"
printf '%s\n' "$IMAGE_ID" >"$OUTPUT_DIR/tested-image-id.txt"
printf 'Verified image %s\n' "$IMAGE_ID"
