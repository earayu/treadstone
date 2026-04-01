#!/usr/bin/env bash
# Guard kubectl context for prod vs local workflows (no auto-switch).
# Usage: check-k8s-context.sh prod | local
#
# TREADSTONE_PROD_CONTEXT — kubeconfig context name for your **production** cluster (not "whatever is current").
#
#   prod:  required. Refuse unless kubectl current-context equals TREADSTONE_PROD_CONTEXT.
#   local: optional. If TREADSTONE_PROD_CONTEXT is set, refuse when current-context equals it
#          (blocks make local / destroy-local while pointed at prod). If unset, skip this check.
set -euo pipefail

mode="${1:-}"
if [[ "$mode" != "prod" && "$mode" != "local" ]]; then
	echo "Usage: $0 prod|local"
	exit 1
fi

current="$(kubectl config current-context 2>/dev/null || true)"
if [[ -z "$current" ]]; then
	# Fresh machine / CI: kubeconfig exists but no context until kind-setup runs (see scripts/up.sh).
	if [[ "$mode" == "local" ]]; then
		echo "OK: no kubectl context yet; kind-setup will create kind-treadstone."
		exit 0
	fi
	echo "ERROR: kubectl has no current context."
	exit 1
fi

if [[ "$mode" == "prod" ]]; then
	if [[ -z "${TREADSTONE_PROD_CONTEXT:-}" ]]; then
		echo "ERROR: TREADSTONE_PROD_CONTEXT is not set."
		echo "Set it to your production cluster's kubectl context name, then switch to it:"
		echo "  export TREADSTONE_PROD_CONTEXT=<prod-context-name>"
		echo "  kubectl config use-context \"\$TREADSTONE_PROD_CONTEXT\""
		exit 1
	fi
	if [[ "$current" != "$TREADSTONE_PROD_CONTEXT" ]]; then
		echo "ERROR: Refusing prod deploy: kubectl current-context is '$current' but TREADSTONE_PROD_CONTEXT is '$TREADSTONE_PROD_CONTEXT'."
		echo "Switch to the production context first:"
		echo "  kubectl config use-context \"$TREADSTONE_PROD_CONTEXT\""
		exit 1
	fi
	echo "OK: kubectl context matches TREADSTONE_PROD_CONTEXT (production)."
	exit 0
fi

# local mode — block local/kind teardown when kubectl points at production (if prod name is configured)
if [[ -n "${TREADSTONE_PROD_CONTEXT:-}" ]]; then
	if [[ "$current" == "$TREADSTONE_PROD_CONTEXT" ]]; then
		echo "ERROR: Refusing local/kind operations: kubectl current-context is the production context ($TREADSTONE_PROD_CONTEXT)."
		echo "Switch to your Kind or other non-production context before running make local or destroy-local."
		exit 1
	fi
	echo "OK: not on production context (TREADSTONE_PROD_CONTEXT=$TREADSTONE_PROD_CONTEXT)."
else
	echo "OK: skipping production-context guard (TREADSTONE_PROD_CONTEXT unset; set it to block accidental local ops on prod)."
fi
