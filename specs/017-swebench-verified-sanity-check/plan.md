# Implementation Plan: SWE-bench Verified Sanity-Check Run

**Branch**: `017-swebench-verified-sanity-check` | **Date**: 2026-09-27 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/017-swebench-verified-sanity-check/spec.md`

## Summary

Add a parallel, single-model mini-SWE-agent run path — new script, new
scaffold config, new execution config — that runs gpt-5-mini (via OpenRouter,
pinned to the OpenAI provider) against 14 named SWE-bench Verified instances
under a $1 total cost cap, grades them with the existing SWE-bench harness
wrapper, and reports a per-instance comparison against the published
`20260217_mini-v2.0.0_gpt-5-mini` leaderboard entry. The existing two-model
Lite sweep (`scripts/run_miniswe_sweep.py`, `configs/option_a.yaml`) is left
untouched; this is additive.

## Technical Context

**Language/Version**: Python 3.10+ (repo also has a 3.14 venv with
mini-swe-agent 2.4.6 installed; leaderboard entry used 2.0.0 — accepted gap,
see spec Assumptions).

**Primary Dependencies**: `mini-swe-agent>=2,<3` (already an optional extra,
`pip install -e ".[agent]"`), `swebench==4.1.0` (already a dependency, used
for grading), `datasets` (HF loader, already used by `hecate.data.tasks`).
No new runtime package.

**Storage**: `data/outputs/runs/verified-sanity-gpt5mini/` — a new run
directory, gitignored like every other `data/outputs/runs/*` — holding
`preds.json`, per-instance `.traj.json`, `generations.jsonl`,
`executions.jsonl`, and manifests. Leaderboard reference data
(`per_instance_details.json`) fetched or cached alongside it.

**Testing**: Unit-test the new argv-building / instance-id-validation /
comparison-table logic with fakes, same pattern as
`tests/test_miniswe_batch.py` (no Docker, no network in the default suite).
Live run is operator-triggered, matching Principle III.

**Target Platform**: Same as the existing agent sweep — local dry-run,
Docker-backed live run (x86 `namespace: swebench` images; `--platform
linux/amd64` on arm64 hosts).

**Project Type**: Thin CLI scripts + small additions to the existing
`hecate.agent` / `hecate.execution` library modules.

**Performance Goals**: 14 instances, sequential, single model, $1 hard cap —
smoke-scale, not a sweep.

**Constraints**: Exact 14-id set; fail loudly on any missing id; $1 total
cap enforced before new spend, not just checked after the fact; existing
Lite two-model path must keep working unmodified.

**Scale/Scope**: One new script, one new benchmark config, one new
execution config, one small additive change to `hecate.agent.batch`, one
narrow fix to `hecate.execution.runner` to stop requiring a large-tier
model slug when only one model is configured, one new comparison script.

## Constitution Check

*GATE: Evaluated against constitution v1.0.0.*

| Principle | Verdict | Basis |
|-----------|---------|-------|
| I. Execution-Grounded Validity | **PASS (by existing precedent)** | Labels come from `swebench.harness.run_evaluation`, not agent self-report (FR-012). The scaffold itself is agentic/multi-turn, which reads against the literal "single-shot generation (v1)" invariant — but this repo already carries that exception for the whole mini-SWE-agent path (`docs/agent-pipeline.md`, commit `14032c0`), explicitly kept out of the Lite single-shot `generations.jsonl`. This feature is a single-model instance of that same already-accepted parallel path, not a new deviation. |
| II. Reproducibility by Manifest | **PASS** | New run writes a manifest with config snapshot, model slug, git commit, timestamp, mini-swe-agent version, total cost, and the leaderboard reference id (mirrors `run_miniswe_sweep.py`'s existing manifest shape). |
| III. Offline-Testable, Zero-Spend CI | **PASS** | New argv-building, id-validation, and comparison-table logic are unit-tested with fakes; the live run is operator-invoked, not part of `pytest` default collection. |
| IV. Spec-Driven Development | **PASS** | This spec + plan; every FR above maps to a task in tasks.md. |
| V. Budget Discipline | **PASS** | New, tighter cap ($1 total) than anything else in the repo; enforced via `MSWEA_GLOBAL_COST_LIMIT` + sequential (`--workers 1`) execution so it binds before new spend, not after. |
| VI. Secrets Hygiene | **PASS** | Reuses `hecate.utils.env.load_env()` / existing `OPENROUTER_API_KEY` convention; no new credential handling. |
| VII. Shared-Scaffold Fairness | **N/A** | Single model, not a comparative matrix — this run validates harness correctness against an external reference, not routing fairness between models. |

**Result: GREEN — no violations.**

## Project Structure

### Documentation (this feature)

```text
specs/017-swebench-verified-sanity-check/
├── plan.md
├── spec.md
└── tasks.md
```

### Source Code (repository root)

```text
configs/
├── miniswe_verified_single.yaml   # new: benchmark config for this run
└── execution_verified.yaml        # new: grading config, Verified dataset

scripts/
├── run_verified_sanity.py         # new: single-model, 14-id, $1-capped runner
└── compare_verified_leaderboard.py # new: per-instance comparison report

src/hecate/
├── agent/
│   └── batch.py                   # add optional model_class passthrough
└── execution/
    └── runner.py                  # only require a large-tier slug when >1 model configured

tests/
├── test_verified_sanity.py        # new: argv building, id validation, fakes
└── test_compare_verified_leaderboard.py  # new: comparison table logic
```

**Structure Decision**: Follows the existing agent-scaffold layout
(`scripts/run_miniswe_sweep.py` + `configs/miniswe.yaml` + `configs/option_a.yaml`)
as a parallel, single-model sibling rather than parameterizing the existing
sweep script for a non-tiered model — the sweep script's tier-cost-limit
split and `_agent_model()` prefixing are load-bearing for the real two-model
sweep and shouldn't be bent to fit a one-off 14-instance check.

## Design Notes

**Model / cost wiring** (per FR-003/004/005/009, using litellm's cost
calculator per the operator's explicit choice — not the OpenRouter-native
model class): keep the default `LitellmModel` path. `configs/miniswe_verified_single.yaml`:

```yaml
agent:
  step_limit: 250
  cost_limit: 1.0        # upstream requires the field; the real gate is the global cap below
model:
  model_name: openrouter/openai/gpt-5-mini
  model_kwargs:
    parallel_tool_calls: true
    extra_body:
      reasoning:
        effort: medium
      provider:
        order: ["openai"]
        allow_fallbacks: false
```
Checked against OpenRouter's docs directly (not guessed): OpenRouter's
unified reasoning param is the nested `reasoning: {effort: ...}` object —
there is no top-level `reasoning_effort` field on their API, so it goes
under `extra_body` (the field litellm forwards verbatim to the underlying
provider call) alongside `provider`, not as a bare `model_kwargs` key.
gpt-5-mini already defaults to `medium` on OpenRouter, so this pins the
reference run's behavior rather than changing it. (Keep
`agent.system_template`/`instance_template`/`environment` copied verbatim
from the installed `swebench.yaml` — upstream drops its default config
entirely once any `-c` override is passed, so this file must be a full
replacement, not a diff.) No `temperature` key — matches the reference
run's un-overridden default (see spec Assumptions), and litellm's existing
`drop_params: true` (carried over in `model_kwargs`) protects against a
rejected param either way.

**Dataset** (FR-001/002/015): `scaffold.subset: verified`,
`scaffold.split: test` in a `configs/miniswe.yaml`-shaped block read by the
new script; before invoking `mini-extra`, load
`hecate.data.tasks.load_swebench_verified()` locally and assert all 14 ids
(see spec.md "Fixed Instance Set") are present — raise/exit nonzero naming
any missing id, before building the `mini-extra` argv (so a bad id never
reaches a paid call). Pass the ids to `mini-extra swebench --filter
'^(matplotlib__matplotlib-26113|django__django-12741|sympy__sympy-11618|scikit-learn__scikit-learn-25931|sphinx-doc__sphinx-8120|pytest-dev__pytest-7324|pydata__xarray-2905|psf__requests-1921|psf__requests-1766|astropy__astropy-14182|django__django-16642|django__django-12308|mwaskom__seaborn-3187|pylint-dev__pylint-4661)$'`
(exact-set regex; no id-list flag exists upstream). Hardcode the id list as a
constant in `scripts/run_verified_sanity.py` (module-level tuple), not a CLI
argument — this run is pinned to exactly this set.

**Cost cap** (FR-007/008): `run_swebench_batch(..., global_cost_limit=1.0)`
already threads `MSWEA_GLOBAL_COST_LIMIT` into the subprocess env
(`src/hecate/agent/batch.py:133-139`, unchanged). New script hardcodes
`workers=1` (not a flag) — `swebench.py`'s batch loop submits every instance
to a `ThreadPoolExecutor` up front and `--workers` only bounds concurrency,
so `workers=1` is what makes the global check ("before starting each task")
correct; with more workers, several in-flight tasks could each independently
push past the cap before any of them observes it. Once the cap trips, the
in-flight instance's `RuntimeError` is caught by mini-SWE-agent's own
`process_instance` (per-instance try/except) and recorded as an empty
submission; every subsequent queued instance fails on its first model call
for $0 additional spend. Document this in the run's README rather than
building extra pre-check/skip logic for it.

**`hecate.agent.batch.build_swebench_batch_argv` / `run_swebench_batch`**:
add `model_class: str | None = None`, appended as `--model-class`,
`<value>` when set. Default `None` preserves the existing sweep script's
behavior exactly (it never passes this arg).

**`hecate.execution.runner.load_execution_config`**: line ~249
unconditionally calls `_slug_for_tier(option_a, "large")`, which raises when
no large-tier model is configured. Fix: only resolve a large-tier slug when
`len(_ordered_slugs(option_a)) > 1`; for the single-model case, set both
`m1_slug`/`m2_slug` to the one configured slug (they're only consumed by the
two-arm positive-rate diff, which doesn't run when there's one model). This
is the one shared-path change in this feature — everything else is new
files — so it needs its own test confirming the existing two-model
(`configs/option_a.yaml`) path is unaffected.

**Grading** (FR-012): new `configs/execution_verified.yaml` mirrors
`configs/execution.yaml` but points `dataset_name` at the Verified
equivalent of the existing `SWE-bench/SWE-bench_Lite` naming convention, and
`option_a_config` at a new single-model `configs/option_a_verified.yaml`
(one entry, `tier: small`). Confirm the exact accepted `dataset_name` string
for Verified against the installed `swebench` package (not present in either
local dev venv today — check wherever grading actually runs, e.g. the exec
VM) before trusting it; don't guess by pattern-matching the Lite string.

**Comparison** (FR-013): `scripts/compare_verified_leaderboard.py`:
- Fetches
  `https://raw.githubusercontent.com/SWE-bench/experiments/main/evaluation/verified/20260217_mini-v2.0.0_gpt-5-mini/per_instance_details.json`
  (confirmed live schema: a flat JSON object keyed by instance id, each value
  `{"cost": float, "api_calls": int, "resolved": bool}` — no other fields, no
  nesting). Support a `--leaderboard-file` override for a local cached copy
  (offline test fixture, or if GitHub is unreachable).
- Reads `executions.jsonl` (`resolved`) and `generations.jsonl` (`cost_usd`,
  `decoding_params.api_calls`) from the sanity run's output dir for the same
  14 ids — `api_calls` is the identical field name/meaning the leaderboard
  file uses, so no proxy/approximation is needed for that column.
- Emits one row per id: `instance_id, ours_resolved, leaderboard_resolved,
  match, our_cost_usd, our_api_calls, leaderboard_cost_usd,
  leaderboard_api_calls`, as markdown and CSV, plus totals (our total spend,
  match count/rate out of 14).
- Any id present in the 14-id set but missing from either source is a
  reported row with an explicit `MISSING` marker in place of the missing
  side's fields — never a silently dropped row.

## Complexity Tracking

No constitution violations requiring justification.
