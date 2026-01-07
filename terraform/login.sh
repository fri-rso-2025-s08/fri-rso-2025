#!/usr/bin/env bash

CFG_ARRAY=$(tofu output --json | jq '[.resource_group, .cluster_name | .value]')
az aks get-credentials \
    --resource-group "$(printf '%s' "$CFG_ARRAY" | jq -r '.[0]')" \
    --name "$(printf '%s' "$CFG_ARRAY" | jq -r '.[1]')" \
    --overwrite-existing
