#!/bin/bash
# Run Mistral Vibe on GLM (Z.ai) models through OpenRouter (see run_openrouter.sh).
# Usage: scripts/run_glm.sh [extra harbor run options...]
#   GLM_MODELS="openrouter/<vendor>/<model> .." overrides the default models.
set -euo pipefail

export PROVIDER=glm
export DEFAULT_MODELS="${GLM_MODELS:-openrouter/@preset/glm-eval}"
exec "$(dirname "$0")/run_openrouter.sh" "$@"
