#!/usr/bin/env python3
"""Compare a verified-sanity run against the published leaderboard entry.

Reads this repo's own graded output (executions.jsonl for `resolved`,
generations.jsonl for cost/api_calls) and the leaderboard's
per_instance_details.json for 20260217_mini-v2.0.0_gpt-5-mini, and emits a
per-instance comparison table plus totals (spec 017, FR-013).

Usage:
    python scripts/compare_verified_leaderboard.py --run-dir data/outputs/runs/verified-sanity-gpt5mini
    python scripts/compare_verified_leaderboard.py --run-dir ... --leaderboard-file per_instance_details.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))


LEADERBOARD_URL = (
    "https://raw.githubusercontent.com/SWE-bench/experiments/main/evaluation/"
    "verified/20260217_mini-v2.0.0_gpt-5-mini/per_instance_details.json"
)

MISSING = "MISSING"


@dataclass(frozen=True)
class ComparisonRow:
    instance_id: str
    ours_resolved: bool | str
    leaderboard_resolved: bool | str
    match: bool | str
    our_cost_usd: float | str
    our_api_calls: int | str
    leaderboard_cost_usd: float | str
    leaderboard_api_calls: int | str


def fetch_leaderboard_details(
    *, url: str = LEADERBOARD_URL, local_file: str | Path | None = None
) -> dict[str, dict[str, Any]]:
    """Load ``{instance_id: {cost, api_calls, resolved}}`` from GitHub or disk."""
    if local_file is not None:
        text = Path(local_file).read_text(encoding="utf-8")
    else:
        import httpx

        response = httpx.get(url, timeout=30.0)
        response.raise_for_status()
        text = response.text
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object keyed by instance id, got {type(payload)}")
    return payload


def load_our_results(run_dir: Path) -> dict[str, dict[str, Any]]:
    """Read executions.jsonl (resolved) + generations.jsonl (cost, api_calls)."""
    from hecate.data import read_jsonl

    results: dict[str, dict[str, Any]] = {}

    generations_path = run_dir / "generations.jsonl"
    if generations_path.is_file():
        for record in read_jsonl(generations_path):
            results.setdefault(record.instance_id, {})
            results[record.instance_id]["cost_usd"] = record.cost_usd
            results[record.instance_id]["api_calls"] = record.decoding_params.get(
                "api_calls"
            )

    executions_path = run_dir / "executions.jsonl"
    if executions_path.is_file():
        for record in read_jsonl(executions_path):
            results.setdefault(record.instance_id, {})
            results[record.instance_id]["resolved"] = record.resolved

    return results


def build_comparison(
    instance_ids: list[str],
    ours: dict[str, dict[str, Any]],
    leaderboard: dict[str, dict[str, Any]],
) -> list[ComparisonRow]:
    """Build one row per id; a missing side gets an explicit MISSING marker."""
    rows: list[ComparisonRow] = []
    for instance_id in instance_ids:
        our_entry = ours.get(instance_id)
        lb_entry = leaderboard.get(instance_id)

        our_resolved: bool | str = (
            MISSING if our_entry is None or "resolved" not in our_entry else bool(our_entry["resolved"])
        )
        lb_resolved: bool | str = MISSING if lb_entry is None else bool(lb_entry["resolved"])
        match: bool | str = (
            MISSING
            if our_resolved == MISSING or lb_resolved == MISSING
            else our_resolved == lb_resolved
        )
        rows.append(
            ComparisonRow(
                instance_id=instance_id,
                ours_resolved=our_resolved,
                leaderboard_resolved=lb_resolved,
                match=match,
                our_cost_usd=(our_entry or {}).get("cost_usd", MISSING),
                our_api_calls=(our_entry or {}).get("api_calls", MISSING),
                leaderboard_cost_usd=(lb_entry or {}).get("cost", MISSING),
                leaderboard_api_calls=(lb_entry or {}).get("api_calls", MISSING),
            )
        )
    return rows


def render_markdown(rows: list[ComparisonRow]) -> str:
    header = (
        "| instance_id | ours_resolved | leaderboard_resolved | match | "
        "our_cost_usd | our_api_calls | leaderboard_cost_usd | leaderboard_api_calls |"
    )
    sep = "|---|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for row in rows:
        lines.append(
            f"| {row.instance_id} | {row.ours_resolved} | {row.leaderboard_resolved} | "
            f"{row.match} | {row.our_cost_usd} | {row.our_api_calls} | "
            f"{row.leaderboard_cost_usd} | {row.leaderboard_api_calls} |"
        )
    return "\n".join(lines)


def render_csv(rows: list[ComparisonRow]) -> str:
    header = (
        "instance_id,ours_resolved,leaderboard_resolved,match,our_cost_usd,"
        "our_api_calls,leaderboard_cost_usd,leaderboard_api_calls"
    )
    lines = [header]
    for row in rows:
        lines.append(
            f"{row.instance_id},{row.ours_resolved},{row.leaderboard_resolved},"
            f"{row.match},{row.our_cost_usd},{row.our_api_calls},"
            f"{row.leaderboard_cost_usd},{row.leaderboard_api_calls}"
        )
    return "\n".join(lines)


def summarize(rows: list[ComparisonRow]) -> dict[str, Any]:
    comparable = [r for r in rows if r.match != MISSING]
    matches = sum(1 for r in comparable if r.match is True)
    total_cost = sum(
        r.our_cost_usd for r in rows if isinstance(r.our_cost_usd, (int, float))
    )
    return {
        "total_instances": len(rows),
        "comparable_instances": len(comparable),
        "missing_instances": len(rows) - len(comparable),
        "matches": matches,
        "match_rate": (matches / len(comparable)) if comparable else None,
        "total_our_cost_usd": round(total_cost, 6),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare our SWE-bench Verified sanity run against "
        "20260217_mini-v2.0.0_gpt-5-mini"
    )
    parser.add_argument(
        "--run-dir",
        default="data/outputs/runs/verified-sanity-gpt5mini",
        help="Run directory containing generations.jsonl and executions.jsonl",
    )
    parser.add_argument(
        "--leaderboard-file",
        default=None,
        help="Local cached per_instance_details.json (default: fetch from GitHub)",
    )
    parser.add_argument(
        "--format",
        choices=("markdown", "csv"),
        default="markdown",
    )
    args = parser.parse_args(argv)

    from run_verified_sanity import VERIFIED_INSTANCE_IDS  # type: ignore[import-not-found]

    run_dir = Path(args.run_dir)
    ours = load_our_results(run_dir)
    try:
        leaderboard = fetch_leaderboard_details(local_file=args.leaderboard_file)
    except Exception as exc:  # network/parse failure: fail loudly, not silently
        print(f"error: could not load leaderboard details: {exc}", file=sys.stderr)
        return 1

    rows = build_comparison(list(VERIFIED_INSTANCE_IDS), ours, leaderboard)
    rendered = render_markdown(rows) if args.format == "markdown" else render_csv(rows)
    print(rendered)

    summary = summarize(rows)
    print()
    print(f"total_instances={summary['total_instances']}")
    print(f"missing_instances={summary['missing_instances']}")
    print(f"matches={summary['matches']}/{summary['comparable_instances']}")
    if summary["match_rate"] is not None:
        print(f"match_rate={summary['match_rate']:.3f}")
    print(f"total_our_cost_usd={summary['total_our_cost_usd']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
