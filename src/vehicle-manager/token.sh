#!/usr/bin/env bash

set -euo pipefail

if test -f .env; then
    . .env
fi

curl -X POST "$OAUTH_TOKEN_URL" \
    -d "grant_type=client_credentials" \
    -d "client_id=$OAUTH_CLIENT_ID" \
    -d "username=$OAUTH_USERNAME" \
    -d "password=$OAUTH_PASSWORD" \
    -d "scope=openid profile email tenant"
