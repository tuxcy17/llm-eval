#!/bin/bash
# Reference fix: round the page count up instead of down.
set -euo pipefail

sed -i 's|return total_items // per_page|return -(-total_items // per_page)|' /app/paging/paginate.py
grep -q -- '-(-total_items // per_page)' /app/paging/paginate.py
