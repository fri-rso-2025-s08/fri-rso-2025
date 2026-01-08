#!/usr/bin/env bash

set -euo pipefail
cd "$(dirname -- "$0")"

ENV=$1

tofu init -backend-config="../vars/$ENV/state_storage.tfvars"
