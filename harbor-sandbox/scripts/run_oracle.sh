#!/bin/bash
# Phase 3: run the reference solution (solution/solve.sh) through Harbor.
# Expected: resolved = 1.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "${repo_root}"

harbor run \
    --path tasks/fix-bulk-discount \
    --agent oracle \
    --env docker \
    --jobs-dir jobs \
    --job-name "oracle-$(date +%Y%m%d-%H%M%S)" \
    --n-concurrent 1 \
    "$@"
