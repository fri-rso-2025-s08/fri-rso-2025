#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname -- "$0")"

ENV=$1
shift

tofu "$@" \
    -var-file="../vars/$ENV/state_location.tfvars" \
    -var-file="../vars/$ENV/state_storage.tfvars"
