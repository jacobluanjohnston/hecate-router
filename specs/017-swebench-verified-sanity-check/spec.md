# Feature Specification: SWE-bench Verified Sanity-Check Run

**Feature Branch**: `017-swebench-verified-sanity-check`

**Created**: 2026-09-27

**Status**: Draft

**Input**: Reproduce one published SWE-bench leaderboard result
(`20260217_mini-v2.0.0_gpt-5-mini`, SWE-bench Verified, "Bash Only" /
mini-SWE-agent scaffold, 56.2% resolved) on 14 named instances, using this
repo's existing mini-SWE-agent integration and evaluation harness, to confirm
our harness gives the same pass/fail verdicts as the official one.

## Fixed Instance Set

The 14 SWE-bench Verified instance ids this run is restricted to:

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

## User Scenarios & Testing

### User Story 1 - Run a single model against 14 fixed Verified instances (Priority: P1)

An operator runs one model (gpt-5-mini via OpenRouter) through mini-SWE-agent
against exactly the 14 named SWE-bench Verified instances, and gets back a
patch (or an empty submission) plus cost/step metadata for each, with total
spend bounded regardless of how many instances run.

**Why this priority**: Without this, there is nothing to grade or compare.

**Independent Test**: Run with `--dry-run`; confirm the dataset resolves to
SWE-bench Verified, all 14 requested ids are found, and the constructed argv
uses the single configured model. No network or Docker calls made.

**Acceptance Scenarios**:

1. **Given** the 14 instance ids, **When** the run starts, **Then** it fails
   loudly before issuing any model call if any id is absent from SWE-bench
   Verified's `test` split.
2. **Given** a completed run, **When** the output directory is inspected,
   **Then** it contains one `preds.json` entry and one trajectory file per
   requested instance (empty patch allowed, missing entry is not).
3. **Given** the run is mid-flight, **When** cumulative reported spend
   crosses $1.00, **Then** no further model call is issued and instances
   processed after that point are recorded with an empty patch rather than
   silently dropped.

---

### User Story 2 - Grade the run with the official SWE-bench harness (Priority: P1)

An operator takes the generated patches and evaluates them with the same
`swebench.harness.run_evaluation` invocation this repo already uses for its
Lite sweep, against SWE-bench Verified, producing a resolved/unresolved
verdict per instance.

**Why this priority**: The comparison is meaningless without an
independently-computed resolved verdict from the real harness, not a
self-report from the agent.

**Independent Test**: Feed the 14-instance prediction file through
`run_execution.py` pointed at a Verified-specific execution config; confirm
`executions.jsonl` has exactly 14 rows, each with `resolved` populated.

**Acceptance Scenarios**:

1. **Given** an instance with an empty/no-op patch, **When** graded, **Then**
   it is recorded as not resolved without being sent to the evaluator.
2. **Given** an instance with a patch that applies, **When** graded, **Then**
   `resolved` reflects the harness's own FAIL_TO_PASS/PASS_TO_PASS check, not
   the agent's self-reported exit status.

---

### User Story 3 - Compare our verdicts to the published leaderboard entry (Priority: P1)

An operator gets a per-instance table — our resolved/unresolved vs. the
leaderboard's recorded resolved/unresolved for the same 14 ids — plus a match
rate and total spend, to judge whether this harness reproduces the published
result closely enough to trust it for future runs.

**Why this priority**: This comparison is the entire purpose of the run; P1.

**Independent Test**: Run the comparison script against the leaderboard's
published `per_instance_details.json` for these 14 ids and a local
`executions.jsonl`; confirm it emits one row per id with a match column and
does not silently skip an id present in one side but not the other.

**Acceptance Scenarios**:

1. **Given** both result sets cover all 14 ids, **When** compared, **Then**
   the report shows resolved/unresolved for both sides, a match flag, our
   cost, and our step/API-call count for every id.
2. **Given** an id missing from either side, **When** compared, **Then** the
   report flags it explicitly rather than omitting the row.

### Edge Cases

- An instance id from the 14 is not present in SWE-bench Verified's `test`
  split → fail before any spend, naming the missing id(s).
- The $1 global cap trips mid-run → in-flight instance fails cleanly
  (recorded, not crashed-and-lost); already-produced results are not
  discarded; the run process itself exits without hanging.
- The agent submits no patch for an instance (step/cost limit, crash, no
  `submit`) → still gets a `preds.json`/generation record with an empty
  patch, graded as not-resolved, not dropped from the comparison table.
- OpenRouter routes to a provider other than OpenAI despite the pinned
  `provider.order` → treat as a run defect to investigate, not silently
  accept; the served `model` field logged per response is the check.

## Requirements

### Functional Requirements

- **FR-001**: The run MUST source tasks from `princeton-nlp/SWE-bench_Verified`,
  `test` split — not SWE-bench Lite — for both patch generation and grading.
- **FR-002**: The run MUST be restricted to exactly the 14 named instance
  ids listed in "Fixed Instance Set" above, and MUST fail before issuing any
  model call if one or more of those ids is not found in the dataset.
- **FR-003**: The run MUST use a single model, `gpt-5-mini` via OpenRouter,
  not the existing two-model (small/large tier) configuration.
- **FR-004**: The OpenRouter request MUST pin the provider to OpenAI with no
  fallbacks (`provider: {order: ["openai"], allow_fallbacks: false}`).
- **FR-005**: The OpenRouter request MUST set reasoning effort to `medium`
  explicitly, via the nested `reasoning: {effort: "medium"}` field (OpenRouter's
  unified reasoning param — there is no top-level `reasoning_effort` field).
  gpt-5-mini already defaults to `medium` on OpenRouter, so this is a
  reproducibility pin, not a behavior change.
- **FR-006**: The agent's per-instance step cap MUST be 250, matching the
  reference run's config.
- **FR-007**: The run MUST NOT apply a per-instance dollar cap that would cut
  off a legitimate task short of the reference scaffold's own defaults; it
  MUST instead enforce a single **$1.00 total** cap across the whole run.
- **FR-008**: The $1.00 cap MUST be checked in a way that accounts for
  spend already committed (not just spend from fully-finished instances)
  before any new model call is issued; running instances strictly
  sequentially (one worker) is the accepted way to satisfy this.
- **FR-009**: Cost per response MUST be computed via litellm's cost
  calculator (`litellm.cost_calculator.completion_cost`) — this repo's
  existing default cost-accounting path for the litellm-backed model class —
  applied uniformly to every response in this run.
- **FR-010**: Every model response's served `model` field MUST be captured
  (already present in mini-SWE-agent's persisted trajectory JSON) so the
  actual serving snapshot can be confirmed after the run.
- **FR-011**: The run MUST NOT reuse or merge results into
  `sweep-2x300-mini-swe`'s existing output directory or `generations.jsonl`
  — its own separate run directory.
- **FR-012**: Grading MUST use the existing `swebench.harness.run_evaluation`
  invocation (`src/hecate/execution/harness.py`), pointed at the Verified
  dataset, not a new/duplicate harness call path.
- **FR-013**: The final report MUST be a per-instance table with our
  resolved/unresolved, the leaderboard's resolved/unresolved (from
  `per_instance_details.json` for `20260217_mini-v2.0.0_gpt-5-mini`, fetched
  from
  `https://raw.githubusercontent.com/SWE-bench/experiments/main/evaluation/verified/20260217_mini-v2.0.0_gpt-5-mini/per_instance_details.json`
  — confirmed schema: `{instance_id: {cost, api_calls, resolved}}`, no other
  fields), a match flag, our cost, and our step/API-call count — plus total
  spend and overall match rate. The leaderboard's own `api_calls` field is
  the exact same metric mini-SWE-agent's own trajectory records, so no proxy
  reasoning is needed for that column.
- **FR-014**: Existing two-model sweep code, config, and committed results
  (`scripts/run_miniswe_sweep.py`, `configs/option_a.yaml`,
  `docs/runs/sweep-2x300-mini-swe/`) MUST remain unmodified and functional;
  this feature adds a parallel path rather than replacing it.
- **FR-015**: A dry-run mode MUST exist that verifies dataset loading, the
  14-id filter, and argv/config construction without issuing any model call
  or Docker container.

### Key Entities

- **Sanity-check run directory**: one run's `preds.json`, per-instance
  trajectory files, merged `generations.jsonl`, and a manifest — the
  single-model analog of the existing two-model sweep's output directory.
- **Comparison row**: one instance id's `(ours_resolved, leaderboard_resolved,
  match, cost_usd, api_calls)` tuple, the unit the final report is built from.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All 14 requested instances produce a generation record (patch
  or explicit empty) and a graded `resolved` verdict — zero silently-dropped
  instances.
- **SC-002**: Total recorded spend for the run is ≤ $1.00.
- **SC-003**: The comparison report is produced with all 14 rows populated
  on both sides (ours and leaderboard), and an overall match rate is stated.
- **SC-004**: A dry run completes in well under a minute with zero network
  cost and correctly reports the resolved dataset name/row count and the 14
  matched ids.

## Assumptions

- Installed mini-swe-agent (2.4.6) differs from the leaderboard entry's
  pinned 2.0.0; this is accepted as "close enough" for a sanity check and
  the installed version is recorded in the run manifest rather than pinned
  back to 2.0.0.
- litellm's cost calculator has (or can be given) pricing data for
  `gpt-5-mini`; if not, the existing fail-closed behavior in this repo's
  model wrapper (raise rather than silently record $0) is accepted as-is —
  this feature does not add a fallback cost source.
- The reference run's "temperature 0" describes mini-SWE-agent's own
  un-overridden default for this benchmark config, not a value this feature
  needs to set explicitly; if gpt-5-mini rejects an implicit temperature
  value in practice, that is a finding from the single-instance smoke check,
  not a pre-decided design point.
- SWE-bench Verified capitalization/aliasing between this repo's own loader
  (`princeton-nlp/SWE-bench_Verified`) and mini-SWE-agent's built-in
  `--subset verified` mapping resolve to the same underlying dataset; the
  dry run is expected to catch it if they don't.
