"""Public tests: must pass both before and after the bulk-discount fix."""

from decimal import Decimal

import pytest

from pricing.cart import Cart, Item


def test_subtotal_sums_lines():
    cart = Cart()
    cart.add(Item("pen", Decimal("1.50"), 2))
    cart.add(Item("notebook", Decimal("3.00"), 1))
    assert cart.subtotal() == Decimal("6.00")


def test_empty_cart():
    cart = Cart()
    assert cart.subtotal() == Decimal("0")
    assert cart.total() == Decimal("0.00")


def test_bulk_discount_applies_for_large_quantity():
    cart = Cart()
    cart.add(Item("pen", Decimal("2.00"), 15))
    assert cart.total() == Decimal("27.00")


def test_no_bulk_discount_for_small_quantity():
    cart = Cart()
    cart.add(Item("pen", Decimal("2.00"), 3))
    assert cart.total() == Decimal("6.00")


@pytest.mark.parametrize("quantity", [0, -1])
def test_non_positive_quantity_rejected(quantity):
    with pytest.raises(ValueError):
        Item("pen", Decimal("1.00"), quantity)


def test_negative_price_rejected():
    with pytest.raises(ValueError):
        Item("pen", Decimal("-0.01"), 1)


def test_total_is_rounded_half_up():
    cart = Cart()
    cart.add(Item("gadget", Decimal("0.125"), 1))
    assert cart.total() == Decimal("0.13")
