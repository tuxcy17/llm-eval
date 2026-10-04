#!/bin/bash
# Run Mistral Vibe on DeepSeek models through OpenRouter (see run_openrouter.sh).
# Usage: scripts/run_deepseek.sh [extra harbor run options...]
#   DEEPSEEK_MODELS="openrouter/<vendor>/<model> .." overrides the default models.
set -euo pipefail

export PROVIDER=deepseek
export DEFAULT_MODELS="${DEEPSEEK_MODELS:-openrouter/@preset/deepseek-eval}"
exec "$(dirname "$0")/run_openrouter.sh" "$@"
