#!/bin/bash
# Phase 5: run Claude Code on each task (one harbor run per task, so that
# per-task limits apply), 3 attempts, concurrency 1.
# Auth: subscription token read from CLAUDE_CODE_OAUTH_TOKEN at runtime only.
#
# Usage: [TASKS="a b"] scripts/run_claude.sh <model> [extra harbor run options...]
#   e.g. scripts/run_claude.sh claude-sonnet-5-5
#
# TASKS: space-separated task names (default: every tasks/*/task.toml).
# tasks/<name>/limits.env (generated from the spec) may define MAX_TURNS and
# MAX_BUDGET_USD, passed to the agent as --ak max_turns / max_budget_usd.
# Timeouts live in task.toml and are enforced by Harbor itself.
set -euo pipefail

if [[ $# -lt 1 || "$1" == -* ]]; then
    echo "usage: $0 <model> [extra harbor run options...]" >&2
    exit 2
fi
model="$1"
shift

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

# Read one KEY from limits.env without sourcing it; accepts numbers only.
limit() {
    local file="$1" key="$2" value
    [[ -f "${file}" ]] || return 0
    value="$(sed -n "s/^${key}=//p" "${file}" | tail -n 1)"
    [[ -z "${value}" ]] && return 0
    if [[ ! "${value}" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
        echo "${file}: invalid ${key}=${value}" >&2
        exit 1
    fi
    printf '%s' "${value}"
}

if [[ -n "${TASKS:-}" ]]; then
    read -r -a tasks <<< "${TASKS}"
else
    tasks=()
    for f in tasks/*/task.toml; do
        [[ -f "${f}" ]] || continue
        d="$(dirname "${f}")"
        tasks+=("$(basename "${d}")")
    done
fi
if [[ ${#tasks[@]} -eq 0 ]]; then
    echo "no task found under tasks/" >&2
    exit 1
fi

stamp="$(date +%Y%m%d-%H%M%S)"
failed=()

for task in "${tasks[@]}"; do
    task_dir="tasks/${task}"
    if [[ ! -f "${task_dir}/task.toml" ]]; then
        echo "unknown task: ${task}" >&2
        failed+=("${task}")
        continue
    fi
    job_name="claude-code-${stamp}-${task}"

    kwargs=()
    max_turns="$(limit "${task_dir}/limits.env" MAX_TURNS)"
    max_budget="$(limit "${task_dir}/limits.env" MAX_BUDGET_USD)"
    [[ -n "${max_turns}" ]] && kwargs+=(--ak "max_turns=${max_turns}")
    [[ -n "${max_budget}" ]] && kwargs+=(--ak "max_budget_usd=${max_budget}")
    echo "== ${task}: max_turns=${max_turns:-none} max_budget_usd=${max_budget:-none}"

    # CLAUDE_FORCE_OAUTH=1: Harbor's claude-code agent then forwards only the
    # OAuth token. ANTHROPIC_BASE_URL is dropped so the agent talks to the
    # default Anthropic endpoint (Harbor forwards it otherwise).
    if ! env -u ANTHROPIC_BASE_URL CLAUDE_FORCE_OAUTH=1 \
        harbor run \
        --path "${task_dir}" \
        --agent claude-code \
        --model "${model}" \
        --env docker \
        --jobs-dir jobs \
        --job-name "${job_name}" \
        --n-attempts 3 \
        --n-concurrent 1 \
        "${kwargs[@]}" \
        "$@"; then
        failed+=("${task}")
    fi

    # Safety net: the token must never be written to the job outputs.
    if [[ -d "jobs/${job_name}" ]] && grep -rqF -- "${CLAUDE_CODE_OAUTH_TOKEN}" "jobs/${job_name}"; then
        echo "WARNING: the OAuth token was found in jobs/${job_name}; do not share it." >&2
        exit 1
    fi
    echo "Token leak check passed for jobs/${job_name}."
done

if [[ ${#failed[@]} -gt 0 ]]; then
    echo "harbor run failed for: ${failed[*]}" >&2
    exit 1
fi
