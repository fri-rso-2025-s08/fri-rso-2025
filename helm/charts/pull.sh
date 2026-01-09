#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname -- "$0")"

TARGETS=(*.json)

# If args provided, strip extensions and append .json
if [ "$#" -gt 0 ]; then
    TARGETS=()
    for arg in "$@"; do
        TARGETS+=("${arg%.*}.json")
    done
fi

for f in "${TARGETS[@]}"; do
    repo=$(jq -r .repo "$f")
    name=$(jq -r .name "$f")
    tmp=$(mktemp -d)

    helm pull "$name" --repo "$repo" --destination "$tmp"
    mv "$tmp"/*.tgz "./${f%.json}.tgz"
    rm -rf "$tmp"
done
