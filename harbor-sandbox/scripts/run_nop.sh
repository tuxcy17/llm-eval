#!/bin/bash
# Phase 4: run the agent that does nothing.
# Runs every task under tasks/ (override with TASK=<name> or TASK_PATH=tasks/<name>,
# or filter with e.g. -i "fix-*"). Expected: resolved = 0, p2p = 1 on each task.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "${repo_root}"

if [[ -n "${TASK:-}" ]]; then
    TASK_PATH="tasks/${TASK}"
fi

harbor run \
    --path "${TASK_PATH:-tasks}" \
    --agent nop \
    --env docker \
    --jobs-dir jobs \
    --job-name "nop-$(date +%Y%m%d-%H%M%S)" \
    --n-concurrent 1 \
    "$@"
