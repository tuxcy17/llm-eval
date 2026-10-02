#!/bin/bash
# Phase 4: run the agent that does nothing.
# Runs every task under tasks/ (see run_oracle.sh). Expected: resolved = 0, p2p = 1.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "${repo_root}"

harbor run \
    --path "${TASK_PATH:-tasks}" \
    --agent nop \
    --env docker \
    --jobs-dir jobs \
    --job-name "nop-$(date +%Y%m%d-%H%M%S)" \
    --n-concurrent 1 \
    "$@"
