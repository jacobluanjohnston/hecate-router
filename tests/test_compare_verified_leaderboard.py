"""Offline tests for the leaderboard comparison script (spec 017)."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from hecate.data import GenerationRecord, append_jsonl


def _load_module():
    import sys

    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "compare_verified_leaderboard",
        root / "scripts" / "compare_verified_leaderboard.py",
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    # dataclass() resolves annotations via sys.modules[cls.__module__]; the
    # module must be registered there before exec_module defines the class.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = _load_module()


def _record(instance_id: str, **overrides) -> GenerationRecord:
    base = dict(
        instance_id=instance_id,
        repo="fake/repo",
        base_commit="deadbeef",
        model_slug="openai/gpt-5-mini",
        tier="small",
        prompt=None,
        extracted_patch="diff",
        patch_parse_ok=True,
        cost_usd=0.02,
        decoding_params={"api_calls": 10},
    )
    base.update(overrides)
    return GenerationRecord(**base)


def test_matched_ids_get_correct_match_flag() -> None:
    leaderboard = {
        "id-a": {"cost": 0.03, "api_calls": 12, "resolved": True},
        "id-b": {"cost": 0.01, "api_calls": 5, "resolved": False},
    }
    ours = {
        "id-a": {"resolved": True, "cost_usd": 0.02, "api_calls": 10},
        "id-b": {"resolved": True, "cost_usd": 0.015, "api_calls": 6},
    }
    rows = MODULE.build_comparison(["id-a", "id-b"], ours, leaderboard)
    by_id = {r.instance_id: r for r in rows}
    assert by_id["id-a"].match is True
    assert by_id["id-b"].match is False


def test_id_missing_from_leaderboard_is_flagged_not_dropped() -> None:
    leaderboard: dict = {"id-a": {"cost": 0.03, "api_calls": 12, "resolved": True}}
    ours = {
        "id-a": {"resolved": True, "cost_usd": 0.02, "api_calls": 10},
        "id-b": {"resolved": True, "cost_usd": 0.015, "api_calls": 6},
    }
    rows = MODULE.build_comparison(["id-a", "id-b"], ours, leaderboard)
    by_id = {r.instance_id: r for r in rows}
    assert by_id["id-b"].leaderboard_resolved == MODULE.MISSING
    assert by_id["id-b"].match == MODULE.MISSING
    assert len(rows) == 2  # not silently dropped


def test_id_missing_from_our_results_is_flagged_not_dropped() -> None:
    leaderboard = {
        "id-a": {"cost": 0.03, "api_calls": 12, "resolved": True},
        "id-b": {"cost": 0.01, "api_calls": 5, "resolved": False},
    }
    ours = {"id-a": {"resolved": True, "cost_usd": 0.02, "api_calls": 10}}
    rows = MODULE.build_comparison(["id-a", "id-b"], ours, leaderboard)
    by_id = {r.instance_id: r for r in rows}
    assert by_id["id-b"].ours_resolved == MODULE.MISSING
    assert by_id["id-b"].match == MODULE.MISSING


def test_load_our_results_reads_generations_and_executions(tmp_path: Path) -> None:
    generations = tmp_path / "generations.jsonl"
    executions = tmp_path / "executions.jsonl"
    append_jsonl(generations, _record("id-a", cost_usd=0.021, decoding_params={"api_calls": 9}))
    append_jsonl(executions, _record("id-a", resolved=True))

    results = MODULE.load_our_results(tmp_path)
    assert results["id-a"]["cost_usd"] == 0.021
    assert results["id-a"]["api_calls"] == 9
    assert results["id-a"]["resolved"] is True


def test_fetch_leaderboard_details_reads_local_file(tmp_path: Path) -> None:
    fixture = tmp_path / "per_instance_details.json"
    fixture.write_text(
        json.dumps({"id-a": {"cost": 0.03, "api_calls": 12, "resolved": True}}),
        encoding="utf-8",
    )
    details = MODULE.fetch_leaderboard_details(local_file=fixture)
    assert details["id-a"]["resolved"] is True


def test_summarize_counts_matches_and_excludes_missing() -> None:
    rows = [
        MODULE.ComparisonRow("a", True, True, True, 0.01, 5, 0.01, 5),
        MODULE.ComparisonRow("b", False, True, False, 0.01, 5, 0.01, 5),
        MODULE.ComparisonRow(
            "c", MODULE.MISSING, True, MODULE.MISSING, MODULE.MISSING, MODULE.MISSING, 0.01, 5
        ),
    ]
    summary = MODULE.summarize(rows)
    assert summary["total_instances"] == 3
    assert summary["missing_instances"] == 1
    assert summary["comparable_instances"] == 2
    assert summary["matches"] == 1
    assert summary["match_rate"] == 0.5
