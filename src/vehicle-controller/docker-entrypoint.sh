#!/bin/sh

set -euo pipefail

APP=$1
shift

fastapi run -e vehicle_controller."$APP".default_app:app "$@"
