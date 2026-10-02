"""Hidden FAIL_TO_PASS tests for partial last pages."""

import pytest

from paging.paginate import paginate, total_pages


@pytest.mark.parametrize(
    "total_items, per_page, expected",
    [(25, 10, 3), (21, 10, 3), (1, 10, 1), (9, 10, 1), (0, 10, 0)],
)
def test_total_pages_rounds_up(total_items, per_page, expected):
    assert total_pages(total_items, per_page) == expected


def test_last_partial_page_is_reachable():
    assert paginate(list(range(25)), 3, 10) == [20, 21, 22, 23, 24]


def test_single_short_page():
    assert paginate(["a", "b", "c"], 1, 10) == ["a", "b", "c"]


def test_page_after_last_partial_page_rejected():
    with pytest.raises(ValueError):
        paginate(list(range(25)), 4, 10)
