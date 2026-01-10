#!/bin/sh

set -euo pipefail

pnpm run db:force-push
exec node build
