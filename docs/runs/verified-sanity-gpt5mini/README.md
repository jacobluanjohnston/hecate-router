# verified-sanity-gpt5mini — results

SWE-bench Verified sanity check: gpt-5-mini via OpenRouter through this
repo's mini-SWE-agent scaffold, graded by the existing SWE-bench harness,
compared against the published leaderboard entry
`20260217_mini-v2.0.0_gpt-5-mini` (SWE-bench Verified, "Bash Only", 56.2%
resolved). Run 2026-09-27 on `hecate-exec`. Spec/plan/tasks:
[`../../../specs/017-swebench-verified-sanity-check/`](../../../specs/017-swebench-verified-sanity-check/).

**`matplotlib__matplotlib-26113` is excluded from every number below.** It
failed during Docker container start on the very first attempt (a Ctrl+C
sent mid-cascade of unrelated OpenRouter auth errors killed its `docker run`
with SIGINT before the agent object even existed), never got a real
trajectory, and a gap in the retry tooling (a failed-instance detector that
only checked `.traj.json` files misses instances that fail before agent
creation) meant it was never re-attempted with the fixed API key. It has
zero real attempts against this model — an infra miss, not a model result.
Results below are the 13 instances that actually ran.

## Context

Before trusting this pipeline for a new experiment, needed to confirm it
reproduces a published leaderboard result rather than silently disagreeing
with the official grader.

## Method

Single model, gpt-5-mini via OpenRouter (`openrouter/openai/gpt-5-mini`),
pinned to the OpenAI provider with no fallbacks, reasoning effort set
explicitly to `medium` (OpenRouter's own default for this model — pinned for
reproducibility, not a behavior change). step_limit 250, matching the
reference config. $1.00 total spend cap enforced via
`MSWEA_GLOBAL_COST_LIMIT`, run sequentially (`--workers 1`) so the cap binds
before starting a new instance. 14 named instances spanning
matplotlib/django/sympy/scikit-learn/sphinx/pytest/xarray/requests/astropy/seaborn/pylint.
Graded with the existing `swebench.harness.run_evaluation` wrapper against
`SWE-bench/SWE-bench_Verified`. Installed mini-swe-agent is 2.4.6 vs. the
leaderboard's 2.0.0 — accepted gap, recorded in the run manifest.

## Result

Total spend: **$0.261465** (well under the $1 cap). Match rate: **10/13
(76.9%)** against the leaderboard's resolved/unresolved verdicts.

| instance_id | ours_resolved | leaderboard_resolved | match | our_cost_usd | our_api_calls | leaderboard_cost_usd | leaderboard_api_calls |
|---|---|---|---|---|---|---|---|
| django__django-12741 | False | True | **False** | 0.0208 | 20 | 0.0315 | 21 |
| sympy__sympy-11618 | False | False | True | 0.0154 | 15 | 0.0127 | 9 |
| scikit-learn__scikit-learn-25931 | True | True | True | 0.0172 | 16 | 0.0246 | 11 |
| sphinx-doc__sphinx-8120 | True | True | True | 0.0302 | 23 | 0.0383 | 17 |
| pytest-dev__pytest-7324 | False | False | True | 0.0108 | 12 | 0.0224 | 13 |
| pydata__xarray-2905 | True | False | **False** | 0.0118 | 15 | 0.0340 | 13 |
| psf__requests-1921 | True | True | True | 0.0207 | 19 | 0.0206 | 13 |
| psf__requests-1766 | True | True | True | 0.0125 | 15 | 0.0219 | 12 |
| astropy__astropy-14182 | False | False | True | 0.0134 | 15 | 0.0129 | 11 |
| django__django-16642 | False | False | True | 0.0178 | 15 | 0.0284 | 13 |
| django__django-12308 | False | True | **False** | 0.0252 | 25 | 0.0374 | 18 |
| mwaskom__seaborn-3187 | False | False | True | 0.0447 | 31 | 0.0365 | 17 |
| pylint-dev__pylint-4661 | False | False | True | 0.0208 | 16 | 0.0223 | 11 |

## Interpretation

10/13 agreement, with 3 genuine disagreements, all in the direction of our
run resolving less than the leaderboard except one (`xarray-2905`, where we
resolved and they didn't). No pattern by repo or step count. Plausible
causes, not disambiguated here: temperature is left unpinned on both sides
(matches the reference's own un-overridden default, but that means neither
run is deterministic), and mini-swe-agent 2.4.6 vs. the leaderboard's 2.0.0
is a two-minor-version gap in prompt/scaffold behavior. This is not evidence
the harness disagrees with the official grader — `resolved` is computed by
the same `swebench.harness.run_evaluation` code both here and upstream; the
disagreements are in what patches the agent produced, not in how they were
graded. Good enough to trust this pipeline for future single-shot sanity
checks; not tight enough to treat a 3-instance disagreement as a harness bug
without more repeats.

## Next

- If a clean 14/14 number is ever needed, redo `matplotlib__matplotlib-26113`
  alone (its `preds.json` entry needs clearing first) and re-grade.
- Generalize the retry-detection gap above if this pattern of run gets
  reused (detect failures that never produced a `.traj.json`, not just ones
  that did with a non-`Submitted` exit status).
- Not planning to chase the 3 disagreements further; flag if a future run
  through this same pipeline shows a similar or worse mismatch rate.

## Notes

Comparison script: `scripts/compare_verified_leaderboard.py`. Cost computed
via litellm's `completion_cost` (price-table based, not OpenRouter's own
reported cost — accepted simplification for this run per operator's
explicit choice, see
[`../../../specs/017-swebench-verified-sanity-check/plan.md`](../../../specs/017-swebench-verified-sanity-check/plan.md)).
