# Phase 1 Semantic State v1.5.4 — Implementation Evidence

**Branch:** `phase1-semantic-state-v1.5.4`
**Base commit:** `9883e6c37328a96fcf58d9c59786b4dee4f657e1`
**Status:** read-only review. Not merged, not frozen, not deployed.
**Date:** 2026-10-04

---

## 1. Governing documents

| Document | SHA-256 | Status |
|---|---|---|
| `Sanuvia-Phase1-SemanticState-Architecture-v0.2.md` | `48c56ce4…fc20a0` | Locked, unmodified |
| `Sanuvia-Phase1-SemanticState-v0.2-Technical-Design-v1.5.4.md` | `6e4e05b7…a8de5` | Sealed, **unmodified** — seal re-verified |
| `…-v1.5.4-Addendum-E1.md` | `a06ca426a48aa3750d5395deae202ab839d807387030e5adf5346405bed4533d` | New (errata, see §3) |

The v1.5.4 seal verifies. The trajectory clarification is issued as a separate
addendum so that the seal remains valid.

---

## 2. Commit sequence

| Commit | Summary |
|---|---|
| `e303dc0` | Slice 1 part 1 — deterministic integrity foundation |
| `dba9129` | Slice 1 part 2 — deterministic identity adjudication |
| `8b983f8` | Slice 1 part 3 — engine wired end to end |
| `bcf33fc` | Phase 1 test-contract migration (suite clean under v1.5.4) |
| `1b4f72a` | Root test-contract migration, part 1 |
| `4acfbfd` | Errata E-1 — restore the prediction trajectory carrier |
| `daaaa09` | Review dataset — revise by declared override, preserve the original |
| `8e69169` | Test-contract migration — renderers, isolation, SQLite reruns |
| `4d43d72` | Test-contract migration — harness, review panels, polish |

---

## 3. Prediction trajectory clarification (errata E-1)

Two independent conditions were identified. They are recorded separately
because one masks the other.

**Authority:** Technical Design v1.5.4 Addendum E-1; locked §8 (prediction
lifecycle deferral); R6 (support derivation).

### Condition B — active, not corrected

`test_proposal_trajectory_hint_flows_into_prediction` fails with
`assert 0 == 1` on `len(result.predictions)`.

Measured directly from engine state:

| | |
|---|---|
| Hypothesis created | `hyp-1` — so this is *not* "no hypothesis" |
| Committed support | **0.400** |
| `prediction_support_threshold` | **0.600** (unchanged) |
| R6 derivation | `0 + 0.5 × 0.8 × (1 − 0)` = 0.400 |
| Predictions | `()` |

The authored `initial_support=0.7`, which under pre-R6 derivation crossed 0.600
directly, is no longer consulted. The threshold is unchanged and the fixture is
unchanged. The test is retained unmodified and remains failing, as the standing
record of the R6 threshold consequence. Its disposition requires a governance
decision.

### Condition A — latent, corrected

The v1.5.4 port migration defined `CandidateProposal` as
`(local_ref, statement, signature)`, dropping `predicted_trajectory` alongside
the three fields §2 C genuinely removes. `_RevisionRun.traj_hints` stayed
declared and stayed read, but **nothing ever wrote it** — so authored
trajectories were discarded at the port boundary and every prediction fell back
to its generated description.

Locked §8 defers the prediction lifecycle. A deferral requires existing
behaviour to be preserved unchanged until the governing cycle rules on it;
omitting the carrier discarded content within the deferred scope.

Restored as optional, content-only data on the existing `FutureTrajectory`
type. It confers no support, crosses no threshold, creates no prediction and
carries no identity. The gate is applied **before** any hint is consulted, so a
hint on a sub-threshold lineage is recorded and never read. Parked candidates
create no hypothesis and so record no hint. The prediction write remains inside
`commit_plan` (sole-writer invariant, TD-W1).

Condition B masks Condition A: where no prediction is created, an omitted
carrier produces no observable symptom.

Verification:

* `test_trajectory_hint_survives_the_port_once_r6_support_crosses_the_gate` —
  reaches the threshold through R6 accumulation (a second supporting
  observation, 0.400 → 0.640, against the unchanged 0.600) and asserts that the
  authored description `"distance then repair"` reaches the prediction rather
  than the generated fallback, and that the two observations resolve to one
  lineage.
* `test_trajectory_on_a_proposal_cannot_create_a_prediction` — trajectory
  content on a sub-threshold lineage, with an authored `initial_support` of
  0.95 that R6 does not consult, yields support 0.400 and no prediction. A
  prediction appearing there would indicate that trajectory content had become
  a support-bearing input and that R6 was no longer the sole source of
  support.

The `CandidateProposal` field-set guard remains an exact set equality. It was
widened by one declared field rather than relaxed, so any further field must be
added to the guard explicitly.

---

## 4. Review dataset migration

### Original — preserved, byte-identical

| | |
|---|---|
| Path | `src/sanuvia/adapters/http/review_dataset.py` |
| SHA-256 | `2acca2920c0a213c213abe355a171294e5a69ffa40e4b0324d21f521383fc17d` |
| Size | 28 065 bytes |
| vs base `9883e6c` | **unchanged** |

`test_original_review_dataset_is_untouched_evidence` asserts that its authored
expectations remain the authored values.

**Authority for every applied change: approved rule R6** (support derivation),
Technical Design v1.5.4 §2 C.

### Revised — an override layer, not a copy

`src/sanuvia/adapters/http/review_dataset_revised.py` deep-copies the original
and applies an enumerated list of changes. `assert_only_declared_changes()`
fails if any expectation differs without a declared row, if a declared row
changes nothing, or if any case's **evidence specs** differ. An undeclared
rebaseline is therefore structurally prevented, not merely prohibited.

### Derivation table — every changed expectation

All five applied changes follow from approved rule R6, with two unchanged
inputs: `prediction_support_threshold` (0.600) and
`aggregate_model_uncertainty`.

| # | Case | Step | Field | Before | After | Class | Derivation |
|---|---|---|---|---|---|---|---|
| 1 | competing-resolve | 2 | predictions | `[H_reassurance]` | `[]` | **A2** | R6 opens at `0.5×0.7` = 0.35, not the authored 0.4. Step 2: `0.35 + 0.5×0.7×0.65` = **0.5775** < 0.6. Step 3: `0.5775 + 0.5×0.8×0.4225` = 0.7465 ≥ 0.6 — the prediction appears one step later. |
| 2 | oscillating-evidence | 2 | predictions | `[H_pursue]` | `[]` | **A2** | Same arithmetic: 0.5775 < 0.6. |
| 3 | oscillating-evidence | 3 | predictions | `[H_pursue, H_withdraw]` | `[]` | **A2** | Both rivals stand at 0.5775; neither crosses. The oscillation itself is unaffected. |
| 4 | oscillating-evidence | 4 | predictions | `[H_pursue, H_withdraw]` | `[H_pursue]` | **A2** | H_pursue 0.725 crosses; H_withdraw 0.5775 does not. The leading hypothesis carries the only prediction. |
| 5 | high-uncertainty-converges | 2 | predictions | `[H_anx]` | `[]` | **A2** | Three candidates open at `0.5×0.6` = 0.30. Step 2: `0.30 + 0.5×0.7×0.70` = **0.545** < 0.6. Convergence still occurs, one step later. |

One narrative sentence was corrected to match its step table.
`docs/engineering-review-dataset.md` was brought into agreement with the revised
dataset, verified programmatically, and records the provenance split; its
machine-verification statement would otherwise have been inaccurate.

### Referred to governance — NOT applied

| Case | Step | Field | Authored | Observed | Class |
|---|---|---|---|---|---|
| failed-acquisition | 3 | uncertainty | `down` | `up` (0.400 → 0.472) | **B** |

The arithmetic is certain. Under R6 the step-2 supports are H_topic 0.35,
H_avoidance 0.15, H_external 0.15, giving `((1−0.35)+0.15)/2` = 0.400. Step 3
lifts H_avoidance to `0.15 + 0.5×0.6×0.85` = 0.405, which **overtakes** H_topic
at 0.35, and the unchanged formula gives `((1−0.405)+0.35)/2` = 0.4725.
Pre-R6, the authored 0.4 starting points let H_avoidance reach 0.58 and win
outright, giving 0.41 and a fall.

**Classification rationale.** The derivation is determinate; the behavioural
claim is not. Changing `down` to `up` revises a documented statement about what
this case demonstrates and requires a corresponding narrative revision. The
observed behaviour is consistent with the stated uncertainty intent in
`scoring.py` ("two strongly-supported rivals (genuine competition) → HIGHER
uncertainty"), which step 3 satisfies. Revising a curated review case to
demonstrate the opposite trend is a governance decision, outside implementation
scope. Left unchanged, so the expectation remains failing and the item remains
open. The case's stated purpose — competing candidates rather than a single
default — is unaffected.

---

## 5. Classification of all 28 pre-existing failures

**M** — mechanical migration (fixture-authored identifier to engine-issued
identifier) · **A1** — R6 numeric consequence · **A2** — R6 threshold
consequence · **D** — approved v1.5.4 rule · **B** — requires governance
decision · **U** — unexplained

| # | Test | Class | Cause | Disposition |
|---|---|---|---|---|
| 1 | `test_review_dataset[competing-resolve]` | A2 | prediction one step later | revised dataset |
| 2 | `test_review_dataset[oscillating-evidence]` | A2 | steps 2–4 predictions | revised dataset |
| 3 | `test_review_dataset[high-uncertainty-converges]` | A2 | step 2 predictions | revised dataset |
| 4 | `test_review_dataset[failed-acquisition]` | **B** | uncertainty trend reverses | **Open** |
| 5 | `test_failed_acquisition_yields_multiple_candidates` | M | fixture-authored identifiers | resolved through lineage attribution; additionally asserts 3 lineages |
| 6 | `test_expected_vs_actual_all_match_for_dataset_case` | **D** | comparison used fixture-authored identifiers against engine-issued identifiers | implementation defect corrected (§6) |
| 7 | `test_reasoning_unchanged_and_expectations_persist_on_save` | **D** | same cause as #6 | implementation defect corrected (§6) |
| 8 | `test_uncertainty_series_from_timeline` | A1 | R6 offset | values recomputed; monotonic fall re-asserted |
| 9 | `test_hypothesis_evolution_series` | M + A1 | identifiers and opening support | resolved; 0.35 / 0.15 derived |
| 10 | `test_prediction_lifecycle_events` | M | fixture-authored identifiers | resolved |
| 11 | `test_add_does_not_run_until_run_next` | M | fixture-authored identifiers | resolved |
| 12 | `test_add_and_run_sequence_consolidates` | M | fixture-authored identifiers | resolved (support 0.626 ≥ 0.600; prediction still forms) |
| 13 | `test_new_and_switch_test_cases_are_isolated` | M | fixture-authored identifiers | resolved |
| 14 | `test_trace_graph_reflect_test_case_reference_is_canonical` | M | fixture-authored identifiers | discriminator changed to authored statements (§6) |
| 15 | `test_live_server_sqlite_backend_across_threads` | D | consequence of #6 | resolved by the #6 correction |
| 16–19 | `test_trace_graph_space` (4) | M | fixture-authored identifiers | identifier read from store state (backend-independent) |
| 20 | `test_reasoning_summary_generated_from_state` | M | fixture-authored identifiers | resolved |
| 21 | `test_explain_why_from_state` | M + A1 | identifiers; 0.87 → 0.86 | resolved; value derived |
| 22 | `test_review_result_pass_for_dataset_case` | A2 | consequence of the dataset revision | resolved by the revised dataset |
| 23 | `test_original_duplicate_id_failure_reproduced` | **D** | collision detected pre-write as a governed outcome | expected exception type updated; additionally asserts no write occurred |
| 24 | `test_durable_sqlite_defaults_to_collision_safe_ids…` | **D** | test double could not resolve its own reference across sessions | corrected in the double via the `catalogue` parameter |
| 25 | `test_two_subjects_same_space_are_isolated` | M | fixture-authored identifiers | asserts disjoint identifier sets |
| 26 | `test_trace_is_generated_from_real_engine_state` | A1 | 0.380 → 0.370; 0.308→0.415 becomes 0.292→0.425 | values derived; fall-then-rise re-asserted |
| 27 | `test_graph_reflects_real_engine_lineage` | M + A1 | node identifier and support series | node identified by the lineage relation |
| 28 | `test_proposal_trajectory_hint_flows_into_prediction` | **B** | R6 threshold consequence (Condition B, §3) | **Open** |

No **B** item was changed. No **U** items were identified: every failure
resolved to an approved rule or to a defect with an identified cause.

---

## 6. Changes to implementation code

Two changes fall outside test code and are recorded separately.

1. **`CandidateProposal.predicted_trajectory` restored** (errata E-1, §3).
2. **`TestCase.authored_to_durable()`** — the expected-vs-actual comparison
   used fixture-authored identifiers while the implementation uses
   engine-issued identifiers, producing a mismatch on every dataset case for a
   reason unrelated to the reasoning under review. The comparison executes
   after identity adjudication and must therefore resolve lineage identity
   before comparing.

   Resolution is by **statement**, which both sides author. This is the basis
   `ScriptedAppraiser` already uses for authored references, and the only basis
   available on the SQLite backend, which carries no semantic-state lineage
   stores. A statement authored by more than one proposal is left unresolved
   rather than inferred; an unresolved identifier remains authored and compares
   unequal, making the condition observable.

   This restores the comparison's defined semantics under engine-issued
   identity. No panel, field or output shape changed.

One test required a different discriminator rather than identity resolution.
`test_trace_graph_reflect_test_case_reference_is_canonical` contrasted a test
case's trace against the canonical reference using fixture-authored
identifiers, which were globally unique. Engine-issued identifiers are
allocated per subject in sequence, so both traces contain `hyp-1` and `hyp-2`,
and an identifier-based contrast would no longer discriminate. The test now
contrasts the authored statements.

---

## 7. Test results

| Suite | Result |
|---|---|
| **Phase 0 exit gate** | **8 / 8 conditions pass** |
| Root (`tests/`) | **281 passed, 2 failed** |
| Phase 1 (`sanuvia-phase1/tests/`) | **152 passed, 0 failed** |
| Semantic-state suites | 76 passed |

The two root failures are items 4 and 28, both classification **B** and both
held open. No test was weakened, skipped, deleted or relaxed, and no threshold,
fixture or engine behaviour was changed to make a test pass.

Mutation protections from Slice 1 remain in force, including the R1a
stance-inversion guard and the `commit_plan` sole-writer assertions.

---

## 8. Repository-repair evidence (verified against base `9883e6c`)

An earlier `git add -A` incorrectly staged 35 Run 001/002 evidence files. The
repair is independently verifiable:

```
git diff --name-only 9883e6c HEAD -- sanuvia-phase1/local_run001 \
                                      sanuvia-phase1/local_run002
→ (empty)
```

The three files tracked at base are **blob-identical** at base and at HEAD:

| File | Blob (base = HEAD) |
|---|---|
| `llama_server_backend_run002.py` | `f3c7835e1a440e718cc717ca5e33243e5603a112` |
| `run002_case001_harness.py` | `ff8f5cd5e2acce724e3ecbe0a8097fe796986f6b` |
| `run002_gate1.py` | `4cc3ae994bb222b4e1e4202a01d09ab5f007ed2f` |

The seven pre-existing untracked evidence paths remain untracked and unstaged:

```
?? sanuvia-phase1/local_run001/
?? sanuvia-phase1/local_run002/README_FOR_REVIEW.txt
?? sanuvia-phase1/local_run002/_superseded/
?? sanuvia-phase1/local_run002/evidence_case001/
?? sanuvia-phase1/local_run002/evidence_preseal/
?? sanuvia-phase1/local_run002/run002_final_evidence_v0.7.tar.gz
?? sanuvia-phase1/local_run002/run002_final_evidence_v0.7.tar.gz.sha256
```

No push occurred before the repair, so it remained local throughout. File
contents on disk were not modified: `git add` affects only the index.

---

## 9. Scope boundaries observed

Out of scope and not performed: Case 002 access or use; Run 003 preparation or
execution; modification of Run 002 evidence; rerun or tuning of Case 001;
changes to model, provider or prompts; retries; repair or normalisation logic;
frontend or product redesign; new identity heuristics.

Architecture v0.2 is unchanged. Technical Design v1.5.4 is unchanged; the
trajectory clarification is issued as separate Addendum E-1. The branch is not
merged, not frozen and not deployed.

---

## 10. Open items for governance

1. **`dataset-failed-acquisition` step 3 uncertainty trend** — authored `down`,
   observed `up` (0.400 → 0.472). Derivation in §4.
2. **`test_proposal_trajectory_hint_flows_into_prediction`** — under R6 a single
   0.8-reliability observation yields 0.400, below the unchanged 0.600
   threshold, so no prediction forms. Derivation in §3.

Both are recorded, both remain failing, neither was changed.

Recorded for completeness, requiring no decision: `REFINE_EXISTING` remains
unreachable because the R1 model-assisted resolver is scoped to Slice 2. With
no resolver configured, a plausible-but-inexact candidate parks as
`AMBIGUOUS_REVIEW_REQUIRED` rather than committing on an unresolved judgement,
as §2 G specifies.
