#!/bin/bash
# Run Mistral Vibe on Mistral models through OpenRouter (see run_openrouter.sh).
# Usage: scripts/run_mistral.sh [extra harbor run options...]
#   MISTRAL_MODELS="openrouter/<vendor>/<model> .." overrides the default models.
set -euo pipefail

export PROVIDER=mistral
export DEFAULT_MODELS="${MISTRAL_MODELS:-openrouter/@preset/mistral-eval}"
exec "$(dirname "$0")/run_openrouter.sh" "$@"
