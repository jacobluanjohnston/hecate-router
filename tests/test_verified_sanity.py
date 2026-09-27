"""Offline tests for the SWE-bench Verified sanity-check run (spec 017)."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest


def _load_module():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location(
        "run_verified_sanity", root / "scripts" / "run_verified_sanity.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


_MODULE = _load_module()
VERIFIED_INSTANCE_IDS = _MODULE.VERIFIED_INSTANCE_IDS
validate_instance_ids = _MODULE.validate_instance_ids


def test_fixed_instance_set_has_fourteen_unique_ids() -> None:
    assert len(VERIFIED_INSTANCE_IDS) == 14
    assert len(set(VERIFIED_INSTANCE_IDS)) == 14


def test_validate_instance_ids_passes_when_all_present() -> None:
    validate_instance_ids(VERIFIED_INSTANCE_IDS, set(VERIFIED_INSTANCE_IDS))


def test_validate_instance_ids_fails_loudly_on_missing_id() -> None:
    dataset_ids = set(VERIFIED_INSTANCE_IDS) - {VERIFIED_INSTANCE_IDS[0]}
    with pytest.raises(ValueError, match=VERIFIED_INSTANCE_IDS[0]):
        validate_instance_ids(VERIFIED_INSTANCE_IDS, dataset_ids)


def _fake_task(instance_id: str):
    from hecate.data.tasks import SwebenchTask

    return SwebenchTask(
        instance_id=instance_id,
        repo="fake/repo",
        base_commit="deadbeef",
        problem_statement="boom",
        patch="",
    )


def test_dry_run_reports_dataset_and_matched_ids_no_network_calls(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = _load_module()
    monkeypatch.chdir(Path(__file__).resolve().parents[1])

    fake_tasks = [_fake_task(iid) for iid in module.VERIFIED_INSTANCE_IDS]

    with patch(
        "hecate.data.tasks.load_swebench_verified", return_value=fake_tasks
    ), patch("hecate.agent.batch.require_miniswe"), patch(
        "hecate.agent.batch.subprocess.run"
    ) as run:
        rc = module.main(
            [
                "--dry-run",
                "--output-dir",
                str(tmp_path / "out"),
            ]
        )

    assert rc == 0
    # require_miniswe() is an import-guard, not a network/Docker call; it
    # runs even in --dry-run (matches run_swebench_batch's existing
    # behavior). subprocess.run is the one that must never fire.
    run.assert_not_called()
    out = capsys.readouterr().out
    assert "matched_ids=14" in out


def test_dry_run_fails_before_any_call_when_id_missing(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    module = _load_module()
    monkeypatch.chdir(Path(__file__).resolve().parents[1])

    missing_id = module.VERIFIED_INSTANCE_IDS[0]
    fake_tasks = [
        _fake_task(iid) for iid in module.VERIFIED_INSTANCE_IDS if iid != missing_id
    ]

    with patch(
        "hecate.data.tasks.load_swebench_verified", return_value=fake_tasks
    ), patch("hecate.agent.batch.subprocess.run") as run:
        rc = module.main(["--dry-run", "--output-dir", str(tmp_path / "out")])

    assert rc == 2
    run.assert_not_called()
    err = capsys.readouterr().err
    assert missing_id in err


def test_argv_uses_single_sequential_worker_and_global_cap(
    tmp_path: Path, monkeypatch
) -> None:
    module = _load_module()
    monkeypatch.chdir(Path(__file__).resolve().parents[1])

    fake_tasks = [_fake_task(iid) for iid in module.VERIFIED_INSTANCE_IDS]

    captured = {}
    real_build = None
    from hecate.agent import batch as batch_mod

    real_build = batch_mod.build_swebench_batch_argv

    def spy_build(**kwargs):
        captured.update(kwargs)
        return real_build(**kwargs)

    with patch(
        "hecate.data.tasks.load_swebench_verified", return_value=fake_tasks
    ), patch("hecate.agent.batch.require_miniswe"), patch(
        "hecate.agent.batch.subprocess.run"
    ), patch(
        "hecate.agent.batch.build_swebench_batch_argv", side_effect=spy_build
    ):
        module.main(["--dry-run", "--output-dir", str(tmp_path / "out")])

    assert captured["workers"] == 1
    assert captured["subset"] == "verified"
    assert captured["split"] == "test"
    for iid in module.VERIFIED_INSTANCE_IDS:
        assert iid in captured["filter_spec"]
