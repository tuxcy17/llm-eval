#!/usr/bin/env python3
"""Extract per-trial metrics from Harbor job directories into a CSV file.

Layout observed with Harbor 0.23.0 (see docs/REPORT.md):

    jobs/<job_name>/result.json                  job-level summary
    jobs/<job_name>/<trial_name>/result.json     trial result (TrialResult)
    jobs/<job_name>/<trial_name>/verifier/reward.json
    jobs/<job_name>/<trial_name>/agent/trajectory.json   (ATIF, LLM agents only)

Every field is optional: missing files or keys yield empty cells.

The CSV is a long-term history: by default new trials are merged into the
existing file (key: job + trial) and rows whose job directory no longer exists
are kept. Use --replace to rebuild the file from jobs/ only.

`task_checksum` identifies the exact task content (instruction, tests,
environment): only trials with the same checksum are comparable.
"""

import argparse
import csv
import fnmatch
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

COLUMNS = [
    "job",
    "trial",
    "task",
    "started_at",
    "agent",
    "model",
    "agent_version",
    "harbor_version",
    "task_checksum",
    "status",
    "resolved",
    "f2p",
    "p2p",
    "n_steps",
    "total_prompt_tokens",
    "total_completion_tokens",
    "total_cached_tokens",
    "total_cost_usd",
    "duration_sec",
    "env_setup_sec",
    "agent_setup_sec",
    "agent_exec_sec",
    "verifier_sec",
    "exception_type",
    "exception_message",
]

FINAL_METRICS_KEYS = [
    "total_prompt_tokens",
    "total_completion_tokens",
    "total_cached_tokens",
    "total_cost_usd",
]

# TrialResult.agent_result fallbacks when no ATIF trajectory is available.
AGENT_RESULT_FALLBACKS = {
    "total_prompt_tokens": "n_input_tokens",
    "total_completion_tokens": "n_output_tokens",
    "total_cached_tokens": "n_cache_tokens",
    "total_cost_usd": "cost_usd",
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def get(data: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def seconds_between(span: Any) -> float | None:
    start, end = get(span, "started_at"), get(span, "finished_at")
    if not start or not end:
        return None
    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    except ValueError:
        return None
    return round(delta.total_seconds(), 2)


def is_trial_result(data: Any) -> bool:
    return isinstance(data, dict) and "trial_name" in data


def extract_trial(
    job_name: str, trial_dir: Path, result: dict, harbor_version: str | None = None
) -> dict:
    row: dict[str, Any] = {key: None for key in COLUMNS}
    row["job"] = job_name
    row["trial"] = result.get("trial_name", trial_dir.name)
    row["task"] = result.get("task_name") or row["trial"].rsplit("__", 1)[0]
    row["task_checksum"] = result.get("task_checksum")
    row["started_at"] = result.get("started_at")
    row["harbor_version"] = harbor_version
    row["agent_version"] = get(result, "agent_info", "version")
    row["agent"] = get(result, "agent_info", "name") or get(
        result, "config", "agent", "name"
    )
    row["model"] = get(result, "agent_info", "model_info", "name") or get(
        result, "config", "agent", "model_name"
    )

    rewards = get(result, "verifier_result", "rewards")
    reward_file = load_json(trial_dir / "verifier" / "reward.json")
    if isinstance(reward_file, dict):
        rewards = reward_file
    if isinstance(rewards, dict) and rewards:
        row["status"] = "ok"
        for key in ("resolved", "f2p", "p2p"):
            row[key] = rewards.get(key)
    else:
        row["status"] = "infra_error"

    trajectory = load_json(trial_dir / "agent" / "trajectory.json")
    final_metrics = get(trajectory, "final_metrics") or {}
    steps = get(trajectory, "steps")
    if isinstance(steps, list):
        row["n_steps"] = len(steps)
    elif final_metrics.get("total_steps") is not None:
        row["n_steps"] = final_metrics["total_steps"]
    for key in FINAL_METRICS_KEYS:
        value = final_metrics.get(key)
        if value is None:
            value = get(result, "agent_result", AGENT_RESULT_FALLBACKS[key])
        row[key] = value
    if row["model"] is None:
        row["model"] = get(trajectory, "agent", "model_name")

    row["duration_sec"] = seconds_between(result)
    row["env_setup_sec"] = seconds_between(result.get("environment_setup"))
    row["agent_setup_sec"] = seconds_between(result.get("agent_setup"))
    row["agent_exec_sec"] = seconds_between(result.get("agent_execution"))
    row["verifier_sec"] = seconds_between(result.get("verifier"))

    exception = result.get("exception_info")
    if isinstance(exception, dict):
        row["exception_type"] = exception.get("exception_type")
        message = (exception.get("exception_message") or "").strip()
        row["exception_message"] = message.splitlines()[0][:200] if message else ""
    return row


def collect_rows(jobs_dir: Path, job_pattern: str) -> list[dict]:
    rows = []
    for job_dir in sorted(p for p in jobs_dir.iterdir() if p.is_dir()):
        if not fnmatch.fnmatch(job_dir.name, job_pattern):
            continue
        harbor_version = get(load_json(job_dir / "lock.json"), "harbor", "version")
        for trial_dir in sorted(p for p in job_dir.iterdir() if p.is_dir()):
            result = load_json(trial_dir / "result.json")
            if is_trial_result(result):
                rows.append(
                    extract_trial(job_dir.name, trial_dir, result, harbor_version)
                )
    return rows


def load_history(path: Path) -> list[dict]:
    """Rows of an existing CSV, tolerant of older column sets."""
    if not path.is_file():
        return []
    with path.open(newline="") as handle:
        rows = [{key: row.get(key) or None for key in COLUMNS} for row in csv.DictReader(handle)]
    for row in rows:
        if not row["task"] and row["trial"]:
            row["task"] = row["trial"].rsplit("__", 1)[0]
    return rows


def merge_rows(history: list[dict], fresh: list[dict]) -> list[dict]:
    """History first, fresh rows replace same (job, trial) or are appended."""
    fresh_by_key = {(r["job"], r["trial"]): r for r in fresh}
    merged = [fresh_by_key.pop((r["job"], r["trial"]), r) for r in history]
    merged.extend(fresh_by_key.values())
    return merged


def warn_mixed_versions(rows: list[dict]) -> None:
    versions: dict[str, set] = {}
    for row in rows:
        if row["task_checksum"]:
            versions.setdefault(row["task"], set()).add(row["task_checksum"])
    for task, checksums in sorted(versions.items()):
        if len(checksums) > 1:
            print(
                f"WARNING: task '{task}' has {len(checksums)} versions in the history "
                "(different task_checksum): do not compare trials across versions.",
                file=sys.stderr,
            )


def mean(values: list) -> float | None:
    numbers = [v for v in values if isinstance(v, (int, float))]
    return statistics.mean(numbers) if numbers else None


def fmt(value: float | None, digits: int = 1) -> str:
    return "-" if value is None else f"{value:,.{digits}f}"


def print_summary(rows: list[dict]) -> None:
    groups: dict[tuple, list[dict]] = {}
    for row in rows:
        groups.setdefault((row["agent"], row["model"]), []).append(row)

    header = (
        f"{'agent':<14}{'model':<28}{'trials':>7}{'infra':>7}{'resolved':>10}"
        f"{'prompt_tok':>12}{'compl_tok':>11}{'steps':>7}{'dur_s':>8}"
    )
    print(header)
    print("-" * len(header))
    for (agent, model), group in sorted(groups.items(), key=lambda kv: str(kv[0])):
        scored = [r for r in group if r["status"] == "ok"]
        n_infra = len(group) - len(scored)
        resolved = mean([r["resolved"] for r in scored])
        rate = "-" if resolved is None else f"{resolved:.0%}"
        print(
            f"{str(agent):<14}{str(model or '-'):<28}{len(group):>7}{n_infra:>7}"
            f"{rate:>10}"
            f"{fmt(mean([r['total_prompt_tokens'] for r in scored]), 0):>12}"
            f"{fmt(mean([r['total_completion_tokens'] for r in scored]), 0):>11}"
            f"{fmt(mean([r['n_steps'] for r in scored])):>7}"
            f"{fmt(mean([r['duration_sec'] for r in scored])):>8}"
        )
    print("(averages and resolution rate exclude infra_error trials)")


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--jobs-dir", type=Path, default=repo_root / "jobs")
    parser.add_argument(
        "--output", type=Path, default=repo_root / "docs" / "metrics.csv"
    )
    parser.add_argument("--job", default="*", help="glob on job names (default: all)")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="rebuild the CSV from jobs/ only instead of merging into the history",
    )
    args = parser.parse_args()

    if not args.jobs_dir.is_dir():
        print(f"Jobs directory not found: {args.jobs_dir}", file=sys.stderr)
        return 1

    rows = collect_rows(args.jobs_dir, args.job)
    if not rows:
        print(f"No trial found under {args.jobs_dir}", file=sys.stderr)
        return 1

    if not args.replace:
        rows = merge_rows(load_history(args.output), rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{len(rows)} trial(s) written to {args.output}\n")
    print_summary(rows)
    warn_mixed_versions(rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
