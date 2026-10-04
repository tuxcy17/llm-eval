#!/usr/bin/env python3
"""Refresh docs/pricing.csv from docs/presets.toml using OpenRouter's public API.

For each preset, look up the endpoint of the pinned provider in
GET /api/v1/models/<model>/endpoints (no API key needed) and record its price in
dollars per million tokens. extract_metrics.py uses the file to estimate the
cost of trials whose agent reported none. Rerunning overwrites the file; the
fetched_at column dates the prices (git keeps the history).

Usage: scripts/update_pricing.py [--presets FILE] [--output FILE]
"""

import argparse
import csv
import json
import sys
import tomllib
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://openrouter.ai/api/v1/models/{model}/endpoints"
COLUMNS = [
    "preset",
    "name",
    "version",
    "model",
    "provider",
    "tag",
    "input_per_m",
    "output_per_m",
    "cache_read_per_m",
    "fetched_at",
]


def fetch_endpoints(model: str) -> list[dict]:
    with urllib.request.urlopen(API.format(model=model), timeout=30) as response:
        return json.load(response)["data"]["endpoints"]


def per_million(value) -> float | None:
    return None if value in (None, "") else round(float(value) * 1_000_000, 6)


def pick_endpoint(endpoints: list[dict], provider: str, tag: str | None):
    matches = [
        e
        for e in endpoints
        if e["provider_name"].lower() == provider.lower()
        and (tag is None or e.get("tag") == tag)
    ]
    if not matches:
        return None, []
    matches.sort(key=lambda e: float(e["pricing"].get("prompt") or 0))
    prices = {(e["pricing"].get("prompt"), e["pricing"].get("completion")) for e in matches}
    return matches[0], sorted(prices) if len(prices) > 1 else []


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--presets", type=Path, default=repo_root / "docs" / "presets.toml")
    parser.add_argument("--output", type=Path, default=repo_root / "docs" / "pricing.csv")
    args = parser.parse_args()

    presets = tomllib.loads(args.presets.read_text()).get("presets", {})
    if not presets:
        print(f"No preset defined in {args.presets}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    rows, failed = [], False
    for preset, conf in presets.items():
        model, provider, tag = conf["model"], conf["provider"], conf.get("tag")
        try:
            endpoint, ambiguous = pick_endpoint(fetch_endpoints(model), provider, tag)
        except (urllib.error.URLError, KeyError, ValueError) as error:
            print(f"[FAIL] {preset}: cannot fetch {model}: {error}", file=sys.stderr)
            failed = True
            continue
        if endpoint is None:
            print(f"[FAIL] {preset}: no endpoint of provider {provider!r} for {model}", file=sys.stderr)
            failed = True
            continue
        if ambiguous:
            print(
                f"[WARN] {preset}: {provider} has {len(ambiguous)} price tiers for {model}; "
                f"cheapest used (set `tag` to choose)",
                file=sys.stderr,
            )
        pricing = endpoint["pricing"]
        rows.append(
            {
                "preset": preset,
                "name": conf.get("name", ""),
                "version": conf.get("version", ""),
                "model": model,
                "provider": endpoint["provider_name"],
                "tag": endpoint.get("tag", ""),
                "input_per_m": per_million(pricing.get("prompt")),
                "output_per_m": per_million(pricing.get("completion")),
                "cache_read_per_m": per_million(pricing.get("input_cache_read")),
                "fetched_at": now,
            }
        )
        print(f"[OK]   {preset} -> {model} @ {endpoint['provider_name']}: "
              f"in {rows[-1]['input_per_m']} / out {rows[-1]['output_per_m']} / cache {rows[-1]['cache_read_per_m']} $/M")

    if failed:
        print("Pricing file not written (fix the errors above).", file=sys.stderr)
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} preset(s) written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
