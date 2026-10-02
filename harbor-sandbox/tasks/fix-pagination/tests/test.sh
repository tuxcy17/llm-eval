#!/bin/bash
# Verifier: hidden FAIL_TO_PASS tests + public PASS_TO_PASS tests.
# No "set -e": the reward file must always be written.

REWARD_DIR=/logs/verifier
mkdir -p "$REWARD_DIR"

f2p=0
p2p=0

if cd /app; then
    # Overwrite any same-named file the agent may have created.
    mkdir -p /app/tests
    cp -f /tests/test_partial_page.py /app/tests/test_partial_page.py

    echo "=== FAIL_TO_PASS (hidden tests) ==="
    if python -m pytest -rA -p no:cacheprovider tests/test_partial_page.py; then
        f2p=1
    fi

    echo "=== PASS_TO_PASS (public tests) ==="
    if python -m pytest -rA -p no:cacheprovider tests/test_paginate.py; then
        p2p=1
    fi
else
    echo "Cannot cd into /app" >&2
fi

resolved=$((f2p * p2p))
printf '{"resolved": %d, "f2p": %d, "p2p": %d}\n' "$resolved" "$f2p" "$p2p" \
    > "$REWARD_DIR/reward.json"
cat "$REWARD_DIR/reward.json"
exit 0
