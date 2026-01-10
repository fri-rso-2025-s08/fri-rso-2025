#!/usr/bin/env bash

set -euo pipefail

pnpm install
pnpm run check
pnpm run test
