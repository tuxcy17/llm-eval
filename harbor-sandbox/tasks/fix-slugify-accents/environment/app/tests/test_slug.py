"""Public tests: must pass both before and after the fix."""

from textutils.slug import slugify


def test_simple_title():
    assert slugify("Hello World") == "hello-world"


def test_collapses_separators():
    assert slugify("a  --  b") == "a-b"


def test_strips_edges():
    assert slugify("  !Hello! ") == "hello"


def test_keeps_digits():
    assert slugify("Top 10 of 2024") == "top-10-of-2024"


def test_empty_string():
    assert slugify("") == ""
