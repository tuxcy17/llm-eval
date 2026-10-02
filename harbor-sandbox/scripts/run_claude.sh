#!/bin/bash
# Phase 5: run Claude Code on every task under tasks/ for each model in MODELS,
# one after the other: 3 attempts per task and model, concurrency 1.
# TASK_PATH=tasks/<name> targets one task; harbor filters such as -i "fix-*" are passed through.
# Auth: subscription token read from CLAUDE_CODE_OAUTH_TOKEN at runtime only.
#
# Usage: scripts/run_claude.sh [extra harbor run options...]
#   Models to evaluate: edit MODELS below, or override for one invocation:
#   CLAUDE_MODELS="claude-haiku-4-5-20251001" scripts/run_claude.sh
set -euo pipefail

MODELS=(
    claude-opus-5-5
    claude-sonnet-5-5
    claude-haiku-4-5-20251001
)
if [[ -n "${CLAUDE_MODELS:-}" ]]; then
    read -r -a MODELS <<< "${CLAUDE_MODELS}"
fi

if [[ ${#MODELS[@]} -eq 0 ]]; then
    echo "No model to evaluate (MODELS is empty)." >&2
    exit 2
fi
if [[ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
    echo "CLAUDE_CODE_OAUTH_TOKEN is not set (run 'claude setup-token')." >&2
    exit 1
fi
for var in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN; do
    if [[ -n "${!var:-}" ]]; then
        echo "${var} is set and would take precedence over the subscription; unset it." >&2
        exit 1
    fi
done

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "${repo_root}"

run_model() {
    local model="$1"
    shift
    local job_name="claude-code-${model}-$(date +%Y%m%d-%H%M%S)"

    echo "=== ${model} -> jobs/${job_name} ==="
    # CLAUDE_FORCE_OAUTH=1: Harbor's claude-code agent then forwards only the
    # OAuth token. ANTHROPIC_BASE_URL is dropped so the agent talks to the
    # default Anthropic endpoint (Harbor forwards it otherwise).
    env -u ANTHROPIC_BASE_URL CLAUDE_FORCE_OAUTH=1 \
        harbor run \
        --path "${TASK_PATH:-tasks}" \
        --agent claude-code \
        --model "${model}" \
        --env docker \
        --jobs-dir jobs \
        --job-name "${job_name}" \
        --n-attempts 3 \
        --n-concurrent 1 \
        "$@"

    # Safety net: the token must never be written to the job outputs.
    if grep -rqF -- "${CLAUDE_CODE_OAUTH_TOKEN}" "jobs/${job_name}"; then
        echo "WARNING: the OAuth token was found in jobs/${job_name}; do not share it." >&2
        return 1
    fi
    echo "Token leak check passed for jobs/${job_name}."
}

failed=()
for model in "${MODELS[@]}"; do
    # A failing model must not prevent the next ones from being evaluated.
    run_model "${model}" "$@" || failed+=("${model}")
done

if (( ${#failed[@]} > 0 )); then
    echo "Failed model(s): ${failed[*]}" >&2
    exit 1
fi
echo "All models evaluated: ${MODELS[*]}"
