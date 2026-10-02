FROM python:3.12-slim

# git is installed only if the base image lacks it (see README: CA shim).
RUN if ! command -v git >/dev/null 2>&1; then \
        apt-get update \
        && apt-get install -y --no-install-recommends git \
        && rm -rf /var/lib/apt/lists/*; \
    fi \
    && pip install --no-cache-dir pytest

COPY app/ /app/
WORKDIR /app

# Single commit of the buggy state: no fix in history.
RUN git init -q \
    && git config user.name "harbor-sandbox" \
    && git config user.email "harbor-sandbox@example.invalid" \
    && git add -A \
    && git commit -q -m "initial import"
