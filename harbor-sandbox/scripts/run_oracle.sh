#!/bin/bash
# Phase 3: run the reference solution (solution/solve.sh) through Harbor.
# Runs every task under tasks/ (override with TASK=<name> or TASK_PATH=tasks/<name>,
# or filter with e.g. -i "fix-*"). Expected: resolved = 1 on each task.
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "${repo_root}"

if [[ -n "${TASK:-}" ]]; then
    TASK_PATH="tasks/${TASK}"
fi

harbor run \
    --path "${TASK_PATH:-tasks}" \
    --agent oracle \
    --env docker \
    --jobs-dir jobs \
    --job-name "oracle-$(date +%Y%m%d-%H%M%S)" \
    --n-concurrent 1 \
    "$@"
