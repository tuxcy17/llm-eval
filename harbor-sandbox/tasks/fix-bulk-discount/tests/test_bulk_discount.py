"""Hidden FAIL_TO_PASS tests for the bulk-discount boundary."""

from decimal import Decimal

from pricing.cart import Cart, Item


def test_quantity_ten_is_discounted():
    cart = Cart()
    cart.add(Item("pen", Decimal("2.00"), 10))
    assert cart.total() == Decimal("18.00")


def test_quantity_nine_is_not_discounted():
    cart = Cart()
    cart.add(Item("pen", Decimal("2.00"), 9))
    assert cart.total() == Decimal("18.00")


def test_mixed_cart_total():
    cart = Cart()
    cart.add(Item("pen", Decimal("2.50"), 10))
    cart.add(Item("notebook", Decimal("4.99"), 2))
    # 25.00 - 2.50 + 9.98
    assert cart.total() == Decimal("32.48")
