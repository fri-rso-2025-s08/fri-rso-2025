#!/usr/bin/env bash

set -euo pipefail

if test -f .env; then
    . .env
fi

CLEAN_URL=$(echo "$DATABASE_URL" | sed -E 's/^postgresql\+[^:]+:/postgresql:/')

if [ -z "$CLEAN_URL" ]; then
    echo "Error: Failed to parse connection string."
    exit 1
fi

exec pgcli "$CLEAN_URL"
