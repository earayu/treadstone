#!/usr/bin/env bash
# Export pod logs from a Kubernetes namespace to a local directory (for offline grep / incident review).
#
# Usage:
#   ./scripts/export-k8s-logs.sh
#   KUBECTL_CONTEXT=my-cluster NAMESPACE=my-ns TAIL=20000 ./scripts/export-k8s-logs.sh
#
# Output: repo-root/logs/k8s-export/<UTC-timestamp>/<pod-name>.log

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_BASE="${OUT_BASE:-$ROOT/logs/k8s-export}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${OUT_BASE}/${STAMP}"
KUBECTL_CONTEXT="${KUBECTL_CONTEXT}"
NAMESPACE="${NAMESPACE:-treadstone-prod}"
TAIL="${TAIL:-15000}"

mkdir -p "$OUT"
echo "Writing logs to $OUT (context=$KUBECTL_CONTEXT ns=$NAMESPACE tail=$TAIL)"

PODS=()
while IFS= read -r line; do
  [[ -n "$line" ]] && PODS+=("$line")
done < <(kubectl --context="$KUBECTL_CONTEXT" get pods -n "$NAMESPACE" -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')

if [[ ${#PODS[@]} -eq 0 ]]; then
  echo "No pods found in $NAMESPACE" >&2
  exit 1
fi

for pod in "${PODS[@]}"; do
  safe="${pod//\//-}"
  dest="$OUT/${safe}.log"
  echo "  $pod -> $(basename "$dest")"
  # --all-containers: include initContainers (e.g. sandbox init-home) in one stream
  if ! kubectl --context="$KUBECTL_CONTEXT" logs -n "$NAMESPACE" "$pod" \
    --all-containers=true --tail="$TAIL" --timestamps 2>&1 >"$dest"; then
    echo "    (failed)" >&2
  fi
done

echo "Done. Latest export: $OUT"
ls -la "$OUT"
