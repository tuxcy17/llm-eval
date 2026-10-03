#!/bin/bash
# Phase 5: run Claude Code on every task under tasks/ for each model in MODELS,
# one after the other: 3 attempts per task and model. One harbor run per task
# (job claude-code-<model>-<timestamp>-<task>) so that per-task limits apply.
# Concurrency: N_CONCURRENT trials at once (default 3), i.e. the attempts of a task.
# TASKS="a b" selects tasks by name; TASK_PATH=tasks/<name> targets one task;
# harbor filters such as -i "fix-*" are passed through.
# tasks/<name>/limits.env (generated from the spec) may define MAX_TURNS and
# MAX_BUDGET_USD, passed to the agent as --ak max_turns / max_budget_usd.
# Timeouts live in task.toml and are enforced by Harbor itself.
# Auth: subscription token read from CLAUDE_CODE_OAUTH_TOKEN at runtime only.
#
# Usage: scripts/run_claude.sh [extra harbor run options...]
#   Models to evaluate: edit MODELS below, or override for one invocation:
#   CLAUDE_MODELS="claude-haiku-4-5-20251001" scripts/run_claude.sh
#   Parallel trials: N_CONCURRENT=1 scripts/run_claude.sh (default 3)
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
elif [[ -n "${TASK_PATH:-}" ]]; then
    tasks=("$(basename "${TASK_PATH}")")
else
    tasks=()
    for f in tasks/*/task.toml; do
        [[ -f "${f}" ]] || continue
        tasks+=("$(basename "$(dirname "${f}")")")
    done
fi
if [[ ${#tasks[@]} -eq 0 ]]; then
    echo "No task found under tasks/." >&2
    exit 1
fi

run_task() {
    local model="$1" task="$2" stamp="$3"
    shift 3
    local task_dir="tasks/${task}"
    local job_name="claude-code-${model}-${stamp}-${task}"

    if [[ ! -f "${task_dir}/task.toml" ]]; then
        echo "Unknown task: ${task}" >&2
        return 1
    fi

    local kwargs=() max_turns max_budget
    max_turns="$(limit "${task_dir}/limits.env" MAX_TURNS)"
    max_budget="$(limit "${task_dir}/limits.env" MAX_BUDGET_USD)"
    [[ -n "${max_turns}" ]] && kwargs+=(--ak "max_turns=${max_turns}")
    [[ -n "${max_budget}" ]] && kwargs+=(--ak "max_budget_usd=${max_budget}")
    echo "== ${model} / ${task}: max_turns=${max_turns:-none} max_budget_usd=${max_budget:-none} -> jobs/${job_name}"

    # CLAUDE_FORCE_OAUTH=1: Harbor's claude-code agent then forwards only the
    # OAuth token. ANTHROPIC_BASE_URL is dropped so the agent talks to the
    # default Anthropic endpoint (Harbor forwards it otherwise).
    env -u ANTHROPIC_BASE_URL CLAUDE_FORCE_OAUTH=1 \
        harbor run \
        --path "${task_dir}" \
        --agent claude-code \
        --model "${model}" \
        --env docker \
        --jobs-dir jobs \
        --job-name "${job_name}" \
        --n-attempts 3 \
        --n-concurrent "${N_CONCURRENT:-3}" \
        "${kwargs[@]}" \
        "$@" || return 1

    # Safety net: the token must never be written to the job outputs.
    if grep -rqF -- "${CLAUDE_CODE_OAUTH_TOKEN}" "jobs/${job_name}"; then
        echo "WARNING: the OAuth token was found in jobs/${job_name}; do not share it." >&2
        exit 1
    fi
    echo "Token leak check passed for jobs/${job_name}."
}

stamp="$(date +%Y%m%d-%H%M%S)"
failed=()
for model in "${MODELS[@]}"; do
    for task in "${tasks[@]}"; do
        # A failing task or model must not prevent the next ones from running.
        run_task "${model}" "${task}" "${stamp}" "$@" || failed+=("${model}/${task}")
    done
done

if (( ${#failed[@]} > 0 )); then
    echo "Failed run(s): ${failed[*]}" >&2
    exit 1
fi
echo "All runs completed: ${MODELS[*]} x ${tasks[*]}"
