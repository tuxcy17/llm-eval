#!/bin/bash
# Phase 0: check the local prerequisites. Never prints secret values.
set -uo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
failures=0

ok()   { printf '  [OK]   %s\n' "$1"; }
fail() { printf '  [FAIL] %s\n' "$1"; failures=$((failures + 1)); }
warn() { printf '  [WARN] %s\n' "$1"; }

echo "Checking prerequisites..."

if docker info >/dev/null 2>&1 && docker run --rm hello-world >/dev/null 2>&1; then
    ok "Docker daemon reachable, hello-world runs"
else
    fail "Docker not usable (docker run hello-world failed)"
fi

if docker compose version >/dev/null 2>&1; then
    ok "docker compose available ($(docker compose version --short 2>/dev/null))"
else
    fail "docker compose plugin missing (Harbor's docker environment needs it)"
fi

if command -v harbor >/dev/null 2>&1; then
    ok "Harbor installed (version $(harbor --version 2>/dev/null))"
else
    fail "harbor not found in PATH (uv tool install harbor)"
fi

if [[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]]; then
    ok "CLAUDE_CODE_OAUTH_TOKEN is set (value not shown)"
else
    fail "CLAUDE_CODE_OAUTH_TOKEN is not set (run 'claude setup-token' and export it)"
fi

for var in ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN; do
    if [[ -n "${!var:-}" ]]; then
        fail "${var} is set: it would take precedence over the subscription token"
    else
        ok "${var} is not set"
    fi
done

if [[ -n "${MISTRAL_API_KEY:-}" ]]; then
    ok "OPENROUTER_API_KEY is set (value not shown)"
else
    warn "OPENROUTER_API_KEY is not set (only needed for run_mistral/deepseek/glm.sh)"
fi

if [[ -n "${ANTHROPIC_BASE_URL:-}" ]]; then
    warn "ANTHROPIC_BASE_URL is set: Harbor forwards it to the agent (run_claude.sh unsets it)"
fi

if [[ -s "${repo_root}/docs/harbor-run-help.txt" ]]; then
    ok "docs/harbor-run-help.txt present"
else
    fail "docs/harbor-run-help.txt missing (COLUMNS=200 harbor run --help > docs/harbor-run-help.txt)"
fi

if (( failures > 0 )); then
    echo "${failures} prerequisite(s) missing."
    exit 1
fi
echo "All prerequisites satisfied."
