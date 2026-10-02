#!/bin/bash
# Phase 4: run the agent that does nothing.
# Expected: resolved = 0, p2p = 1.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "${repo_root}"

harbor run \
    --path tasks/fix-bulk-discount \
    --agent nop \
    --env docker \
    --jobs-dir jobs \
    --job-name "nop-$(date +%Y%m%d-%H%M%S)" \
    --n-concurrent 1 \
    "$@"
