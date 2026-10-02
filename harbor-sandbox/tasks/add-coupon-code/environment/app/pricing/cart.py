"""Shopping cart with a per-line bulk discount."""

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal

BULK_THRESHOLD = 10
BULK_DISCOUNT_RATE = Decimal("0.10")
CENT = Decimal("0.01")


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

    def add(self, item: Item) -> None:
        self.items.append(item)

    def subtotal(self) -> Decimal:
        return sum((item.line_total() for item in self.items), Decimal("0"))

    def total(self) -> Decimal:
        total = Decimal("0")
        for item in self.items:
            line = item.line_total()
            if item.quantity >= BULK_THRESHOLD:
                line -= line * BULK_DISCOUNT_RATE
            total += line
        return total.quantize(CENT, rounding=ROUND_HALF_UP)
