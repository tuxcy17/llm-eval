"""Hidden FAIL_TO_PASS tests for accented characters."""

import pytest

from textutils.slug import slugify


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Café Crème", "cafe-creme"),
        ("Été à Paris", "ete-a-paris"),
        ("  Déjà vu !  ", "deja-vu"),
        ("Garçon, où êtes-vous ?", "garcon-ou-etes-vous"),
    ],
)
def test_accents_are_stripped(title, expected):
    assert slugify(title) == expected
