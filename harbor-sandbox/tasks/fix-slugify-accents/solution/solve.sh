#!/bin/bash
# Reference fix: strip diacritics (NFKD + drop combining marks) before slugging.
set -euo pipefail

cat > /app/textutils/slug.py <<'PY'
"""Turn free text into URL slugs."""

import re
import unicodedata

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def slugify(text: str) -> str:
    """Lowercase `text`, drop accents, replace runs of other characters with '-'."""
    return _NON_SLUG.sub("-", _strip_accents(text).lower()).strip("-")
PY
