"""Turn free text into URL slugs."""

import re

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    """Lowercase `text`, replace runs of other characters with '-'."""
    return _NON_SLUG.sub("-", text.lower()).strip("-")
