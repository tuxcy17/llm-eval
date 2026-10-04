#!/usr/bin/env python3
"""Render docs/metrics.csv as a self-contained HTML page comparing models.

One bar chart per metric (resolution rate, duration, steps, tokens, cost),
one bar per model, plus a table view. Standard library only; the output has
no external dependency and follows the viewer's light/dark theme.

Runs without a model (oracle, nop) and infra_error trials are ignored.
"""

import argparse
import csv
import html
import re
import statistics
import sys
import tomllib
from pathlib import Path

# Model families, in display order. A family is recognised by its keyword in the
# model id (or in the model behind a preset, see docs/presets.toml). Each family
# keeps its own color slot below, whatever the models present in the CSV.
FAMILIES = ["opus", "sonnet", "haiku", "devstral", "glm", "deepseek"]

# Color slots as (light, dark). Claude = shades of blue (Opus strongest), Devstral =
# orange, GLM = black (near-white in dark mode, to stay visible), DeepSeek = gray.
# The last two slots are fallbacks for models of an unknown family.
SERIES = [("#184a9a", "#2d6cc4"), ("#3b82d6", "#5b9ae8"), ("#8dbbec", "#a6c8f2"),
          ("#eb6834", "#d95926"), ("#0b0b0b", "#f2f2f0"), ("#8c8b87", "#8c8b87"),
          ("#1baf7a", "#199e70"), ("#4a3aa7", "#9085e9")]

# Family -> SERIES index (1-based).
FAMILY_SLOT = {"opus": 1, "sonnet": 2, "haiku": 3, "devstral": 4, "glm": 5, "deepseek": 6}
FALLBACK_SLOTS = [7, 8]  # models of an unknown family, in order of appearance

# (key, title, unit label, formatter, per-model value from rows)
METRICS = [
    ("resolved", "Taux de résolution", "% des essais résolus", lambda v: f"{v:.0%}"),
    ("duration", "Durée moyenne", "secondes par essai", lambda v: f"{v:,.0f} s"),
    ("steps", "Étapes moyennes", "étapes par essai", lambda v: f"{v:,.1f}"),
    ("tokens", "Tokens moyens", "prompt + completion par essai", lambda v: f"{v:,.0f}"),
    ("cost", "Coût moyen", "USD par essai", lambda v: f"${v:,.3f}"),
]

CSS = """
:root{color-scheme:light;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;@LIGHT@}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--surface:#1a1a19;
--ink:#fff;--ink2:#c3c2b7;--grid:#363633;@DARK@}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#363633;@DARK@}
body{margin:0;background:var(--surface);color:var(--ink);font:14px/1.5 system-ui,sans-serif}
main{max-width:960px;margin:0 auto;padding:24px 16px}
h1{font-size:20px;margin:0 0 4px}p.sub{color:var(--ink2);margin:0 0 16px}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin:0 0 24px;color:var(--ink2)}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,400px),1fr));gap:24px}
figure{margin:0}figcaption{font-weight:600}figcaption small{display:block;font-weight:400;color:var(--ink2)}
svg{width:100%;height:auto;display:block}svg text{fill:var(--ink2);font-size:12px}
svg text.v{fill:var(--ink)}.ax{stroke:var(--grid);stroke-width:1}
.overflow{overflow-x:auto;margin-top:32px}table{border-collapse:collapse;width:100%}
th,td{text-align:right;padding:6px 10px;border-bottom:1px solid var(--grid);white-space:nowrap}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}th{color:var(--ink2);font-weight:600}
h2{font-size:15px;margin:32px 0 0}
"""


CSS = (CSS.replace("@LIGHT@", ";".join(f"--s{i}:{c[0]}" for i, c in enumerate(SERIES, 1)))
          .replace("@DARK@", ";".join(f"--s{i}:{c[1]}" for i, c in enumerate(SERIES, 1))))


def load_presets(path: Path) -> dict[str, dict]:
    """docs/presets.toml keyed by preset id (empty when absent)."""
    try:
        return tomllib.loads(path.read_text()).get("presets", {})
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def claude_label(model: str) -> str:
    """claude-haiku-4-5-20251001 -> Haiku 4.5."""
    name = re.sub(r"-\d{8}$", "", model.removeprefix("claude-"))
    family, _, version = name.partition("-")
    return f"{family.capitalize()} {version.replace('-', '.')}".strip()


def describe(model: str, presets: dict[str, dict]) -> dict:
    """Readable label, detail line and family of a model id from the CSV."""
    conf = presets.get(model)
    if conf:
        slug = conf["model"]
        return {"label": conf.get("label") or slug,
                "detail": f"{slug} via {conf['provider']} (preset v{conf.get('version', '?')})",
                "family_key": slug.lower()}
    return {"label": claude_label(model) if model.startswith("claude-") else model,
            "detail": model, "family_key": model.lower()}


def family_of(key: str) -> int | None:
    for index, family in enumerate(FAMILIES):
        if family in key:
            return index
    return None


def num(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def aggregate(csv_path: Path, presets: dict[str, dict]) -> list[dict]:
    with csv_path.open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("model")]
    info = {m: describe(m, presets) for m in {r["model"] for r in rows}}
    models = sorted(info, key=lambda m: (family_of(info[m]["family_key"]) is None,
                                         family_of(info[m]["family_key"]) or 0, m))
    fallback = iter(FALLBACK_SLOTS)
    stats = []
    for model in models:
        family = family_of(info[model]["family_key"])
        slot = FAMILY_SLOT[FAMILIES[family]] if family is not None else next(fallback, 8)
        group = [r for r in rows if r["model"] == model]
        scored = [r for r in group if r["status"] == "ok"]
        tokens = [
            (num(r["total_prompt_tokens"]) or 0) + (num(r["total_completion_tokens"]) or 0)
            if num(r["total_prompt_tokens"]) is not None else None
            for r in scored
        ]
        stats.append({
            "model": model,
            "label": info[model]["label"],
            "detail": info[model]["detail"],
            "slot": slot,
            "trials": len(group),
            "infra": len(group) - len(scored),
            "resolved": mean([num(r["resolved"]) for r in scored]),
            "duration": mean([num(r["duration_sec"]) for r in scored]),
            "steps": mean([num(r["n_steps"]) for r in scored]),
            "tokens": mean(tokens),
            "cost": mean([num(r["total_cost_usd"]) for r in scored]),
        })
    return stats


def bar_path(x: float, y: float, w: float, h: float, r: float = 4) -> str:
    """Bar with a rounded data end (right) and a square baseline (left)."""
    r = min(r, w, h / 2)
    return (f"M{x:.1f},{y:.1f}h{w - r:.1f}a{r},{r} 0 0 1 {r},{r}v{h - 2 * r:.1f}"
            f"a{r},{r} 0 0 1 -{r},{r}h-{w - r:.1f}z")


def chart(stats: list[dict], key: str, title: str, unit: str, fmt) -> str:
    present = stats
    if not any(s[key] is not None for s in stats):
        return ""
    width, label_w, right_pad, row_h, bar_h = 400, 132, 60, 34, 20
    top = 6
    height = top + row_h * len(present)
    vmax = 1.0 if key == "resolved" else max(s[key] for s in present if s[key] is not None) or 1.0
    span = width - label_w - right_pad
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
             f'<line class="ax" x1="{label_w}" x2="{label_w}" y1="{top}" y2="{height}"/>']
    for i, s in enumerate(present):
        y = top + i * row_h + (row_h - bar_h) / 2
        if s[key] is None:
            parts.append(f'<text x="{label_w - 8}" y="{y + bar_h / 2 + 4:.1f}" text-anchor="end">'
                         f'{html.escape(s["label"])}</text>')
            parts.append(f'<text x="{label_w + 8}" y="{y + bar_h / 2 + 4:.1f}" font-style="italic">'
                         f'aucun essai valide ({s["infra"]}/{s["trials"]} en erreur infra)</text>')
            continue
        w = max(s[key] / vmax * span, 2)
        tip = f"{s['label']} : {fmt(s[key])} ({s['detail']})"
        parts.append(f'<text x="{label_w - 8}" y="{y + bar_h / 2 + 4:.1f}" text-anchor="end">'
                     f'{html.escape(s["label"])}</text>')
        parts.append(f'<path d="{bar_path(label_w, y, w, bar_h)}" fill="var(--s{s["slot"]})">'
                     f'<title>{html.escape(tip)}</title></path>')
        parts.append(f'<text class="v" x="{label_w + w + 8:.1f}" y="{y + bar_h / 2 + 4:.1f}">'
                     f'{fmt(s[key])}</text>')
    parts.append("</svg>")
    return (f"<figure><figcaption>{html.escape(title)}<small>{html.escape(unit)}</small>"
            f"</figcaption>{''.join(parts)}</figure>")


def table(stats: list[dict]) -> str:
    head = ["Modèle", "Détail", "Essais", "Infra", *[m[1] for m in METRICS]]
    out = ["<div class='overflow'><table><thead><tr>"
           + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for s in stats:
        cells = [html.escape(s["label"]), html.escape(s["detail"]), str(s["trials"]), str(s["infra"])]
        for key, _, _, fmt in METRICS:
            cells.append("-" if s[key] is None else fmt(s[key]))
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render(stats: list[dict]) -> str:
    legend = "".join(
        f'<span><i style="background:var(--s{s["slot"]})"></i>{html.escape(s["label"])}</span>'
        for s in stats)
    charts = "".join(chart(stats, *m) for m in METRICS)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Comparaison des modèles - fix-bulk-discount</title><style>{CSS}</style></head>
<body><main>
<h1>Comparaison des modèles</h1>
<p class="sub">Tâche fix-bulk-discount. Moyennes par modèle, essais en erreur d'infrastructure exclus.</p>
<div class="legend">{legend}</div>
<div class="grid">{charts}</div>
<h2>Tableau</h2>{table(stats)}
</main></body></html>
"""


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=repo_root / "docs" / "metrics.csv")
    parser.add_argument("--presets", type=Path, default=repo_root / "docs" / "presets.toml")
    parser.add_argument("--output", type=Path, default=repo_root / "docs" / "comparison.html")
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"{args.input} not found: run scripts/extract_metrics.py first.", file=sys.stderr)
        return 1
    stats = aggregate(args.input, load_presets(args.presets))
    if not stats:
        print("No trial with a model in the CSV (oracle/nop runs are ignored): "
              "run scripts/run_claude.sh first.", file=sys.stderr)
        return 1
    args.output.write_text(render(stats))
    print(f"{len(stats)} model(s) plotted to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
