#!/usr/bin/env python3
"""Render docs/metrics.csv as a self-contained HTML page comparing models.

One bar chart per metric (resolution rate, duration, steps, tokens, cost),
one bar per model, plus a table view. Standard library only; the output has
no external dependency and follows the viewer's light/dark theme.

Runs without a model (oracle, nop) and infra_error trials are ignored.

Only comparable trials are plotted: for each task, the trials of its latest
version (task_checksum). Older versions and rows without a checksum are
dropped unless --all-versions is given. --task restricts the tasks.
"""

import argparse
import csv
import fnmatch
import html
import re
import statistics
import sys
from pathlib import Path

# Fixed model order, so a model keeps its color whatever the filter.
MODEL_ORDER = ["opus", "sonnet", "haiku"]

# Categorical slots 1-3 (validated all-pairs, light / dark).
SERIES = [("#2a78d6", "#3987e5"), ("#eb6834", "#d95926"), ("#1baf7a", "#199e70"),
          ("#eda100", "#c98500"), ("#e87ba4", "#d55181"), ("#008300", "#008300"),
          ("#4a3aa7", "#9085e9"), ("#e34948", "#e66767")]

# (key, title, unit label, formatter, per-model value from rows)
METRICS = [
    ("resolved", "Taux de résolution", "% des essais résolus", lambda v: f"{v:.0%}"),
    ("duration", "Durée moyenne", "secondes par essai", lambda v: f"{v:,.0f} s"),
    ("steps", "Étapes moyennes", "étapes par essai", lambda v: f"{v:,.1f}"),
    ("tokens", "Tokens moyens", "prompt + completion par essai", lambda v: f"{v:,.0f}"),
    ("cost", "Coût moyen", "USD par essai", lambda v: f"${v:,.3f}"),
]

CSS = """
:root{color-scheme:light;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--grid:#e4e3df;
--s1:#2a78d6;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s6:#008300;--s7:#4a3aa7;--s8:#e34948}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--surface:#1a1a19;
--ink:#fff;--ink2:#c3c2b7;--grid:#363633;--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;
--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767}}
:root[data-theme="dark"]{color-scheme:dark;--surface:#1a1a19;--ink:#fff;--ink2:#c3c2b7;--grid:#363633;
--s1:#3987e5;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s6:#008300;--s7:#9085e9;--s8:#e66767}
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
th:first-child,td:first-child{text-align:left}th{color:var(--ink2);font-weight:600}
h2{font-size:15px;margin:32px 0 0}
"""


def short_name(model: str) -> str:
    """claude-haiku-4-5-20251001 -> haiku-4-5 (full name stays in the table)."""
    return re.sub(r"-\d{8}$", "", model.removeprefix("claude-"))


def order_key(model: str) -> tuple:
    for index, family in enumerate(MODEL_ORDER):
        if family in model:
            return (index, model)
    return (len(MODEL_ORDER), model)


def num(value: str | None) -> float | None:
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def comparable_rows(rows: list[dict], task_glob: str, all_versions: bool) -> list[dict]:
    """Keep the tasks matching the glob and, by default, their latest version only."""
    rows = [r for r in rows if fnmatch.fnmatch(r.get("task") or "", task_glob)]
    if all_versions:
        return rows
    latest: dict[str, tuple[str, str]] = {}
    for r in rows:
        if r.get("task_checksum"):
            stamp = (r.get("started_at") or "", r["task_checksum"])
            latest[r["task"]] = max(latest.get(r["task"], stamp), stamp)
    return [
        r for r in rows
        if r.get("task_checksum") and r["task_checksum"] == latest[r["task"]][1]
    ]


def warn_uneven_tasks(rows: list[dict]) -> None:
    by_model: dict[str, set] = {}
    for r in rows:
        by_model.setdefault(r["model"], set()).add(r["task"])
    if len({frozenset(t) for t in by_model.values()}) > 1:
        detail = "; ".join(f"{m}: {len(t)} task(s)" for m, t in sorted(by_model.items()))
        print(f"WARNING: models were not run on the same tasks ({detail}); "
              "averages are not directly comparable. Use --task to align.", file=sys.stderr)


def aggregate(rows: list[dict]) -> list[dict]:
    models = sorted({r["model"] for r in rows}, key=order_key)
    stats = []
    for slot, model in enumerate(models):
        group = [r for r in rows if r["model"] == model]
        scored = [r for r in group if r["status"] == "ok"]
        tokens = [
            (num(r["total_prompt_tokens"]) or 0) + (num(r["total_completion_tokens"]) or 0)
            if num(r["total_prompt_tokens"]) is not None else None
            for r in scored
        ]
        stats.append({
            "model": model,
            "slot": slot % len(SERIES) + 1,
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
    present = [s for s in stats if s[key] is not None]
    if not present:
        return ""
    width, label_w, right_pad, row_h, bar_h = 400, 96, 64, 34, 20
    top = 6
    height = top + row_h * len(present)
    vmax = 1.0 if key == "resolved" else max(s[key] for s in present) or 1.0
    span = width - label_w - right_pad
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}">',
             f'<line class="ax" x1="{label_w}" x2="{label_w}" y1="{top}" y2="{height}"/>']
    for i, s in enumerate(present):
        y = top + i * row_h + (row_h - bar_h) / 2
        w = max(s[key] / vmax * span, 2)
        tip = f"{short_name(s['model'])} : {fmt(s[key])}"
        parts.append(f'<text x="{label_w - 8}" y="{y + bar_h / 2 + 4:.1f}" text-anchor="end">'
                     f'{html.escape(short_name(s["model"]))}</text>')
        parts.append(f'<path d="{bar_path(label_w, y, w, bar_h)}" fill="var(--s{s["slot"]})">'
                     f'<title>{html.escape(tip)}</title></path>')
        parts.append(f'<text class="v" x="{label_w + w + 8:.1f}" y="{y + bar_h / 2 + 4:.1f}">'
                     f'{fmt(s[key])}</text>')
    parts.append("</svg>")
    return (f"<figure><figcaption>{html.escape(title)}<small>{html.escape(unit)}</small>"
            f"</figcaption>{''.join(parts)}</figure>")


def table(stats: list[dict]) -> str:
    head = ["Modèle", "Essais", "Infra", *[m[1] for m in METRICS]]
    out = ["<div class='overflow'><table><thead><tr>"
           + "".join(f"<th>{html.escape(h)}</th>" for h in head) + "</tr></thead><tbody>"]
    for s in stats:
        cells = [html.escape(s["model"]), str(s["trials"]), str(s["infra"])]
        for key, _, _, fmt in METRICS:
            cells.append("-" if s[key] is None else fmt(s[key]))
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render(stats: list[dict], tasks: list[str]) -> str:
    legend = "".join(
        f'<span><i style="background:var(--s{s["slot"]})"></i>{html.escape(s["model"])}</span>'
        for s in stats)
    charts = "".join(chart(stats, *m) for m in METRICS)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Comparaison des modèles</title><style>{CSS}</style></head>
<body><main>
<h1>Comparaison des modèles</h1>
<p class="sub">{html.escape(', '.join(tasks))}. Moyennes par modèle sur la dernière version de chaque tâche, essais en erreur d'infrastructure exclus.</p>
<div class="legend">{legend}</div>
<div class="grid">{charts}</div>
<h2>Tableau</h2>{table(stats)}
</main></body></html>
"""


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, default=repo_root / "docs" / "metrics.csv")
    parser.add_argument("--output", type=Path, default=repo_root / "docs" / "comparison.html")
    parser.add_argument("--task", default="*", help="glob on task names (default: all)")
    parser.add_argument("--all-versions", action="store_true",
                        help="also plot older task versions and rows without task_checksum")
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"{args.input} not found: run scripts/extract_metrics.py first.", file=sys.stderr)
        return 1
    with args.input.open(newline="") as handle:
        rows = [r for r in csv.DictReader(handle) if r.get("model")]
    rows = comparable_rows(rows, args.task, args.all_versions)
    warn_uneven_tasks(rows)
    stats = aggregate(rows)
    if not stats:
        print("No trial with a model in the CSV (oracle/nop runs are ignored): "
              "run scripts/run_claude.sh first.", file=sys.stderr)
        return 1
    args.output.write_text(render(stats, sorted({r['task'] for r in rows})))
    print(f"{len(stats)} model(s) plotted to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
