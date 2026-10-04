#!/bin/bash
# Shared engine: run Mistral Vibe (Harbor agent "vibe", generic backend) through
# OpenRouter on every task under tasks/ for each model in DEFAULT_MODELS, one after
# the other: 3 attempts per task and model. One harbor run per task (job
# <provider>-vibe-<model>-<timestamp>-<task>) so that per-task limits apply.
# Not meant to be called directly: use run_mistral.sh, run_deepseek.sh or
# run_glm.sh, which set PROVIDER and DEFAULT_MODELS then call this script.
# Concurrency: N_CONCURRENT trials at once (default 3).
# TASKS="a b" selects tasks by name; TASK_PATH=tasks/<name> targets one task;
# harbor filters such as -i "fix-*" are passed through.
# tasks/<name>/limits.env may define MAX_TURNS and MAX_BUDGET_USD, passed to
# the agent as --ak max_turns / max_price (Vibe's --max-turns / --max-price).
# Timeouts live in task.toml and are enforced by Harbor itself.
# Auth: OpenRouter key read from OPENROUTER_API_KEY at runtime only.
# Models are written openrouter/<vendor>/<model>: Harbor strips the first prefix,
# OpenRouter receives <vendor>/<model>.
set -euo pipefail

PROVIDER="${PROVIDER:?PROVIDER is not set (call a run_<provider>.sh wrapper)}"
read -r -a MODELS <<< "${DEFAULT_MODELS:-}"

if [[ ${#MODELS[@]} -eq 0 ]]; then
    echo "No model to evaluate (MODELS is empty)." >&2
    exit 2
fi
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
    echo "OPENROUTER_API_KEY is not set (create one on openrouter.ai/settings/keys)." >&2
    exit 1
fi

# Vibe's generic backend reads the key from OPENAI_API_KEY and needs the endpoint.
export VIBE_BACKEND=generic
export VIBE_API_BASE="${VIBE_API_BASE:-https://openrouter.ai/api/v1}"
export OPENAI_API_KEY="${OPENROUTER_API_KEY}"

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
    local job_name="${PROVIDER}-vibe-${model//\//-}-${stamp}-${task}"

    if [[ ! -f "${task_dir}/task.toml" ]]; then
        echo "Unknown task: ${task}" >&2
        return 1
    fi

    local kwargs=() max_turns max_budget
    max_turns="$(limit "${task_dir}/limits.env" MAX_TURNS)"
    max_budget="$(limit "${task_dir}/limits.env" MAX_BUDGET_USD)"
    [[ -n "${max_turns}" ]] && kwargs+=(--ak "max_turns=${max_turns}")
    [[ -n "${max_budget}" ]] && kwargs+=(--ak "max_price=${max_budget}")
    echo "== ${model} / ${task}: max_turns=${max_turns:-none} max_budget_usd=${max_budget:-none} -> jobs/${job_name}"

    harbor run \
        --path "${task_dir}" \
        --agent vibe \
        --model "${model}" \
        --env docker \
        --jobs-dir jobs \
        --job-name "${job_name}" \
        --n-attempts 3 \
        --n-concurrent "${N_CONCURRENT:-3}" \
        "${kwargs[@]}" \
        "$@" || return 1

    # Safety net: the key must never be written to the job outputs.
    if grep -rqF -- "${OPENROUTER_API_KEY}" "jobs/${job_name}"; then
        echo "WARNING: the API key was found in jobs/${job_name}; do not share it." >&2
        exit 1
    fi
    echo "Key leak check passed for jobs/${job_name}."
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
