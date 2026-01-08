#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname -- "$0")"

CFG_MAP=$(./run.sh "$1" output --json | jq 'map_values(.value)')

cfg_val() {
    printf '%s' "$CFG_MAP" | jq -r ".$1"
}

az aks get-credentials \
    --resource-group "$(cfg_val resource_group)" \
    --name "$(cfg_val cluster_name)" \
    --overwrite-existing

az acr login --name "$(cfg_val registry_name)"
cfg_val registry_login_server > ../../current_registry
