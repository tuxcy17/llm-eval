#!/bin/bash
# Reference implementation of Cart.apply_coupon.
set -euo pipefail

cat > /app/pricing/cart.py <<'PY'
"""Shopping cart with a per-line bulk discount and coupon codes."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

BULK_THRESHOLD = 10
BULK_DISCOUNT_RATE = Decimal("0.10")
CENT = Decimal("0.01")

# code -> (percent rate, fixed amount)
COUPONS: dict[str, tuple[Decimal, Decimal]] = {
    "WELCOME10": (Decimal("0.10"), Decimal("0")),
    "SAVE5": (Decimal("0"), Decimal("5.00")),
}


@dataclass
class Item:
    name: str
    unit_price: Decimal
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity <= 0:
            raise ValueError(f"quantity must be positive, got {self.quantity}")
        if self.unit_price < 0:
            raise ValueError(f"unit_price must be non-negative, got {self.unit_price}")

    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Cart:
    items: list[Item] = field(default_factory=list)
    coupon: str | None = None

    def add(self, item: Item) -> None:
        self.items.append(item)

    def apply_coupon(self, code: str) -> None:
        normalized = code.strip().upper()
        if normalized not in COUPONS:
            raise ValueError(f"unknown coupon code: {code!r}")
        self.coupon = normalized

    def subtotal(self) -> Decimal:
        return sum((item.line_total() for item in self.items), Decimal("0"))

    def total(self) -> Decimal:
        total = Decimal("0")
        for item in self.items:
            line = item.line_total()
            if item.quantity >= BULK_THRESHOLD:
                line -= line * BULK_DISCOUNT_RATE
            total += line
        if self.coupon is not None:
            rate, fixed = COUPONS[self.coupon]
            total = max(total - total * rate - fixed, Decimal("0"))
        return total.quantize(CENT, rounding=ROUND_HALF_UP)
PY
