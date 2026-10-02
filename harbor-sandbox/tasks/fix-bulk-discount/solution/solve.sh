#!/bin/bash
# Reference fix: discount applies from 10 units inclusive (">" -> ">=").
set -euo pipefail

sed -i 's/item\.quantity > BULK_THRESHOLD/item.quantity >= BULK_THRESHOLD/' /app/pricing/cart.py
grep -q 'item.quantity >= BULK_THRESHOLD' /app/pricing/cart.py
