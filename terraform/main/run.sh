#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname -- "$0")"

ENV=$1
shift

tofu "$@" -var-file="../vars/$ENV/main.tfvars"
