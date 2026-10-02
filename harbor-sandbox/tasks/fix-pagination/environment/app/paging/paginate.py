"""Pagination helpers. Pages are numbered from 1."""

from typing import Sequence, TypeVar

T = TypeVar("T")


def total_pages(total_items: int, per_page: int) -> int:
    """Number of pages needed to display `total_items` items."""
    if per_page <= 0:
        raise ValueError(f"per_page must be positive, got {per_page}")
    if total_items < 0:
        raise ValueError(f"total_items must be non-negative, got {total_items}")
    return total_items // per_page


def paginate(items: Sequence[T], page: int, per_page: int) -> list[T]:
    """Return the items of the given 1-indexed page."""
    pages = total_pages(len(items), per_page)
    if page < 1 or page > pages:
        raise ValueError(f"page must be between 1 and {pages}, got {page}")
    start = (page - 1) * per_page
    return list(items[start : start + per_page])
