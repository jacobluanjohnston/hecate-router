# Tasks: SWE-bench Verified Sanity-Check Run

**Input**: Design documents from `/specs/017-swebench-verified-sanity-check/`

**Prerequisites**: plan.md, spec.md

**Tests**: Required (constitution III). Write tests first where noted.

## Format: `[ID] [P?] [Story] Description`

## Phase 1: Setup

- [x] T001 [P] Add `configs/miniswe_verified_single.yaml` — full benchmark
      config (copied `agent.system_template`/`instance_template`/`environment`
      blocks from installed `swebench.yaml`, plus `agent.step_limit: 250`,
      `agent.cost_limit: 1.0`, `model.model_name: openrouter/openai/gpt-5-mini`,
      `model.model_kwargs.extra_body.reasoning.effort: medium` (confirmed
      against OpenRouter's docs: nested `reasoning.effort`, no top-level
      `reasoning_effort` field),
      `model.model_kwargs.extra_body.provider: {order: [openai], allow_fallbacks: false}`)
      — FR-001, FR-003, FR-004, FR-005, FR-006, FR-009
- [x] T002 [P] Add `configs/option_a_verified.yaml` — single model entry
      (`slug: openai/gpt-5-mini`, `tier: small`) — FR-003
- [x] T003 [P] Add `configs/execution_verified.yaml` — `dataset_name` for
      SWE-bench Verified (confirmed against installed `swebench` package's
      accepted name, not guessed), `option_a_config:
      configs/option_a_verified.yaml`, `input_generations:
      data/outputs/runs/verified-sanity-gpt5mini/generations.jsonl` — FR-001, FR-012

---

## Phase 2: Foundational (shared-path changes)

**⚠️ CRITICAL**: blocks User Story 2 (grading a single-model run)

- [x] T004 [US2] Test: `load_execution_config` with a one-model
      `option_a_verified.yaml` does not raise, and `m1_slug == m2_slug` equals
      the sole configured slug; existing two-model `configs/option_a.yaml`
      path still resolves `m1_slug != m2_slug` unchanged, in
      `tests/test_execution.py`
- [x] T005 [US2] Fix `_slug_for_tier`/`load_execution_config` in
      `src/hecate/execution/runner.py` to only require a large-tier slug when
      more than one model is configured (single-model case: both
      `m1_slug`/`m2_slug` = the one slug) — depends on T004

**Checkpoint**: existing two-model execution path unaffected; single-model
config now loads

---

## Phase 3: User Story 1 - Run gpt-5-mini against 14 Verified instances (Priority: P1) 🎯 MVP

**Goal**: single-model, 14-instance, $1-capped mini-SWE-agent run producing
`generations.jsonl` in its own run directory.

**Independent Test**: `python scripts/run_verified_sanity.py --dry-run`
reports the resolved dataset, all 14 matched ids, and the constructed argv,
with zero network/Docker calls.

### Tests for User Story 1

- [x] T006 [P] [US1] Test `build_swebench_batch_argv(..., model_class="litellm")`
      appends `--model-class litellm` when set and omits it (existing
      behavior) when `None`, in `tests/test_miniswe_batch.py`
- [x] T007 [P] [US1] Test the 14-id validator against the fixed set below:
      all-present passes; any missing id raises/exits nonzero naming the
      missing id(s) before any argv is built, in `tests/test_verified_sanity.py`

      ```
      matplotlib__matplotlib-26113
      django__django-12741
      sympy__sympy-11618
      scikit-learn__scikit-learn-25931
      sphinx-doc__sphinx-8120
      pytest-dev__pytest-7324
      pydata__xarray-2905
      psf__requests-1921
      psf__requests-1766
      astropy__astropy-14182
      django__django-16642
      django__django-12308
      mwaskom__seaborn-3187
      pylint-dev__pylint-4661
      ```
- [x] T008 [US1] Test `run_verified_sanity.py --dry-run` argv: single model
      slug, `--filter` regex matches exactly the 14 ids, `--workers 1`,
      `MSWEA_GLOBAL_COST_LIMIT` wired to `1.0`, in `tests/test_verified_sanity.py`

### Implementation for User Story 1

- [x] T009 [P] [US1] Add optional `model_class: str | None = None` param to
      `build_swebench_batch_argv` / `run_swebench_batch` in
      `src/hecate/agent/batch.py` (append `--model-class <value>` when set)
      — FR-003
- [x] T010 [US1] Implement `scripts/run_verified_sanity.py`: load
      `configs/miniswe_verified_single.yaml`, load
      `hecate.data.tasks.load_swebench_verified()`, assert the 14 named ids
      (hardcoded module-level constant — see T007's list) are present (fail
      loudly otherwise), build the `--filter` exact-set
      regex, call `run_swebench_batch(model_class=..., workers=1,
      global_cost_limit=1.0, ...)`, then `read_outcomes` /
      `build_records` / `write_generations` into
      `data/outputs/runs/verified-sanity-gpt5mini/generations.jsonl`, then
      write a manifest (config snapshot, git commit, mini-swe-agent version,
      `leaderboard_reference: "20260217_mini-v2.0.0_gpt-5-mini"`, total cost)
      — FR-002, FR-007, FR-008, FR-010, FR-011, FR-015

**Checkpoint**: US1 dry-run and live single-model generation work
independently of grading/comparison

---

## Phase 4: User Story 2 - Grade with the official harness (Priority: P1)

**Goal**: `executions.jsonl` with a `resolved` verdict per instance, via the
existing `SwebenchHarness` wrapper, on SWE-bench Verified.

**Independent Test**: `python scripts/run_execution.py --config
configs/execution_verified.yaml --input
data/outputs/runs/verified-sanity-gpt5mini/generations.jsonl --output-dir
data/outputs/runs/verified-sanity-gpt5mini` produces 14 rows in
`executions.jsonl`, each with `resolved` set.

### Implementation for User Story 2

- [ ] T011 [US2] Confirm run: `python scripts/run_execution.py --config
      configs/execution_verified.yaml ...` against the T010 output produces
      exactly 14 `executions.jsonl` rows — FR-012 (depends on T003, T005, T010)

**Checkpoint**: US1 + US2 hold; graded verdicts exist for all 14 instances

---

## Phase 5: User Story 3 - Compare against the leaderboard (Priority: P1)

**Goal**: per-instance comparison table + match rate + total spend.

**Independent Test**: run the comparison script against a local copy of
`per_instance_details.json` and the US2 `executions.jsonl`; every id present
on both sides gets a row, any id missing from either side is flagged, not
dropped.

### Tests for User Story 3

- [x] T012 [P] [US3] Test comparison-table builder against a fixture shaped
      like the confirmed leaderboard schema (flat `{instance_id: {cost,
      api_calls, resolved}}`, no other fields): matched ids produce correct
      `match` flag; an id missing from one side gets an explicit `MISSING`
      marker rather than being silently omitted, in
      `tests/test_compare_verified_leaderboard.py`

### Implementation for User Story 3

- [x] T013 [US3] Implement `scripts/compare_verified_leaderboard.py`: read
      `executions.jsonl` (`resolved`) + `generations.jsonl` (`cost_usd`,
      `decoding_params.api_calls`) for the 14 ids; fetch
      `https://raw.githubusercontent.com/SWE-bench/experiments/main/evaluation/verified/20260217_mini-v2.0.0_gpt-5-mini/per_instance_details.json`
      (support `--leaderboard-file` for a local cached copy); emit a
      markdown/CSV table (`instance_id, ours_resolved, leaderboard_resolved,
      match, our_cost_usd, our_api_calls, leaderboard_cost_usd,
      leaderboard_api_calls`) plus total spend and overall match rate —
      FR-013 (depends on T011)

**Checkpoint**: all three user stories independently testable; SC-001–SC-004
verifiable end to end

---

## Phase 6: Polish

- [ ] T014 [P] Add a short README under
      `data/outputs/runs/verified-sanity-gpt5mini/` (or
      `docs/runs/verified-sanity-gpt5mini/README.md` once committed) noting:
      installed mini-swe-agent version vs. the leaderboard's 2.0.0, the
      documented behavior of instances queued after the $1 cap trips
      (recorded with an empty patch, not omitted), and the final match rate
- [x] T015 Confirm `scripts/run_miniswe_sweep.py` and existing
      `tests/test_miniswe_batch.py`/`tests/test_miniswe_agent.py` still pass
      unmodified (FR-014) — regression check for T005/T009. Full suite:
      212 passed, 4 skipped under `.venv312` (Python 3.12). Note: the
      Python 3.14 `.venv` has a pre-existing, unrelated environment bug
      (`datasets`/`dill` pickling incompatible with 3.14's `pickle`
      internals) that fails `test_sweep_writes_a_manifest_per_model` and
      the real `load_swebench_verified()` dry-run identically on a clean
      checkout with none of this feature's changes applied — confirmed via
      `git stash`. Run everything in `.venv312` until that's fixed upstream
      or separately.

---

## Dependencies & Execution Order

- Setup (T001–T003) → Foundational (T004–T005) → US1 (T006–T010) → US2 (T011) → US3 (T012–T013) → Polish
- T004 must fail before T005 lands
- T006–T008 should fail until T009–T010 exist
- T011 depends on T003, T005, T010
- T013 depends on T011

### Parallel opportunities

- T001 / T002 / T003 together
- T006 / T007 together (before T008, which needs both the argv builder and validator)
- T009 independent of T010's script scaffolding, but T010 calls it
- T012 can be written before T013 lands (fails first)

## Implementation Strategy

MVP is US1 (patches generated under the $1 cap, dry-run verifiable). US2
turns those into graded verdicts. US3 is the actual point of the exercise —
the leaderboard comparison — and is the last gate before calling the sanity
check done. Foundational T004/T005 must land first since US2 cannot load a
single-model execution config otherwise.
