#!/bin/bash
# Phase 6: browse the job trajectories in Harbor's web UI.
# The server binds to 127.0.0.1 only: jobs/ holds full agent transcripts.
#
# Usage: scripts/view.sh [extra harbor view options...]
#   e.g. scripts/view.sh --port 9000
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "${repo_root}"

if ! command -v harbor >/dev/null 2>&1; then
    echo "harbor not found in PATH (uv tool install harbor)." >&2
    exit 1
fi
if [[ ! -d jobs ]] || [[ -z "$(ls -A jobs 2>/dev/null)" ]]; then
    echo "jobs/ is empty or missing: run scripts/run_oracle.sh, run_nop.sh or run_claude.sh first." >&2
    exit 1
fi

exec harbor view jobs --host 127.0.0.1 "$@"
