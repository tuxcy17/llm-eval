"""Public tests: must pass both before and after the fix."""

import pytest

from paging.paginate import paginate, total_pages


def test_total_pages_exact_multiple():
    assert total_pages(20, 10) == 2


def test_first_page():
    assert paginate(list(range(20)), 1, 10) == list(range(10))


def test_second_full_page():
    assert paginate(list(range(20)), 2, 10) == list(range(10, 20))


@pytest.mark.parametrize("page", [0, -1, 3])
def test_out_of_range_page_rejected(page):
    with pytest.raises(ValueError):
        paginate(list(range(20)), page, 10)


@pytest.mark.parametrize("per_page", [0, -5])
def test_invalid_per_page_rejected(per_page):
    with pytest.raises(ValueError):
        total_pages(10, per_page)
