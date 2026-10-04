# Phase 1 Semantic State v1.5.4 — Implementation Evidence

**Branch:** `phase1-semantic-state-v1.5.4`
**Base commit:** `9883e6c37328a96fcf58d9c59786b4dee4f657e1`
**Status:** for **read-only review**. Not merged, not frozen, not deployed.
**Date:** 2026-10-04

---

## 1. Governing documents

| Document | SHA-256 | Status |
|---|---|---|
| `Sanuvia-Phase1-SemanticState-Architecture-v0.2.md` | `48c56ce4…fc20a0` | Locked, unmodified |
| `Sanuvia-Phase1-SemanticState-v0.2-Technical-Design-v1.5.4.md` | `6e4e05b7…a8de5` | Sealed, **unmodified** — seal re-verified |
| `…-v1.5.4-Addendum-E1.md` | `b9e0b6621f7e137aa754e9bd9ea63984f700a4ec4b93edffd0c9e5b1b973a9be` | New (errata, see §3) |

The v1.5.4 seal still verifies. The trajectory clarification was written as a
**separate addendum** precisely so it would.

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

The authorization required Case A and Case B be distinguished, not conflated.
**Both were present, and they are independent.**

### Case B — active, NOT repaired

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

The fixture's authored `initial_support=0.7` — which pre-R6 crossed 0.6
directly — is no longer consulted. **The threshold was not altered and the
fixture was not altered.** The test is retained unmodified and still failing,
as the standing record of the R6 threshold consequence. Its disposition is
referred to governance.

### Case A — latent, repaired

The v1.5.4 port migration defined `CandidateProposal` as
`(local_ref, statement, signature)`, dropping `predicted_trajectory` alongside
the three fields §2 C genuinely removes. `_RevisionRun.traj_hints` stayed
declared and stayed read, but **nothing ever wrote it** — so authored
trajectories were discarded at the port boundary and every prediction fell back
to its generated description.

Locked §8 defers the prediction lifecycle. **Deferred means preserved
unchanged, not dropped**: removing the carrier pre-empted the later cycle's
decision rather than deferring it.

Restored as optional, content-only data on the existing `FutureTrajectory`
type. It confers no support, crosses no threshold, creates no prediction and
carries no identity. The gate is applied **before** any hint is consulted, so a
hint on a sub-threshold lineage is recorded and never read. Parked candidates
create no hypothesis and so record no hint. The prediction write remains inside
`commit_plan` (sole-writer invariant, TD-W1).

**Case B was masking Case A**: with no prediction forming at all, the dropped
carrier produced no visible symptom.

Two new tests close it:

* `test_trajectory_hint_survives_the_port_once_r6_support_crosses_the_gate` —
  reaches the gate the governed way (a second observation, 0.4 → 0.64, past the
  unchanged 0.6) and asserts the authored description `"distance then repair"`
  reaches the prediction rather than the fallback, and that **one** lineage
  forms, not two.
* `test_trajectory_on_a_proposal_cannot_create_a_prediction` — a sub-threshold
  lineage with an authored trajectory (and a deliberately high authored
  `initial_support` of 0.95, which R6 ignores) yields support 0.4 and **no**
  prediction. If this ever passes a prediction, the hint has become a
  support-bearing input and R6 is no longer the sole source of support.

The `CandidateProposal` field-set guard was **widened deliberately, not
relaxed**: it remains an exact set equality, so any future field must be added
there and justified.

---

## 4. Review dataset migration

### Original — preserved, byte-identical

| | |
|---|---|
| Path | `src/sanuvia/adapters/http/review_dataset.py` |
| SHA-256 | `2acca2920c0a213c213abe355a171294e5a69ffa40e4b0324d21f521383fc17d` |
| Size | 28 065 bytes |
| vs base `9883e6c` | **unchanged** |

A test (`test_original_review_dataset_is_untouched_evidence`) asserts its
authored expectations are still the authored values.

### Revised — an override layer, not a copy

`src/sanuvia/adapters/http/review_dataset_revised.py` deep-copies the original
and applies an enumerated list of changes. `assert_only_declared_changes()`
fails if any expectation differs without a declared row, if a declared row
changes nothing, or if any case's **evidence specs** were touched at all. A
silent rebaseline is structurally impossible rather than merely discouraged.

### Derivation table — every changed expectation

All five applied changes follow from **one** approved rule (R6) plus two things
that are **unchanged**: `prediction_support_threshold` (0.6) and
`aggregate_model_uncertainty`.

| # | Case | Step | Field | Before | After | Class | Derivation |
|---|---|---|---|---|---|---|---|
| 1 | competing-resolve | 2 | predictions | `[H_reassurance]` | `[]` | **A2** | R6 opens at `0.5×0.7` = 0.35, not the authored 0.4. Step 2: `0.35 + 0.5×0.7×0.65` = **0.5775** < 0.6. Step 3: `0.5775 + 0.5×0.8×0.4225` = 0.7465 ≥ 0.6 — the prediction appears one step later. |
| 2 | oscillating-evidence | 2 | predictions | `[H_pursue]` | `[]` | **A2** | Same arithmetic: 0.5775 < 0.6. |
| 3 | oscillating-evidence | 3 | predictions | `[H_pursue, H_withdraw]` | `[]` | **A2** | Both rivals stand at 0.5775; neither crosses. The oscillation itself is unaffected. |
| 4 | oscillating-evidence | 4 | predictions | `[H_pursue, H_withdraw]` | `[H_pursue]` | **A2** | H_pursue 0.725 crosses; H_withdraw 0.5775 does not. Sharpens the case — the leader carries the only prediction. |
| 5 | high-uncertainty-converges | 2 | predictions | `[H_anx]` | `[]` | **A2** | Three candidates open at `0.5×0.6` = 0.30. Step 2: `0.30 + 0.5×0.7×0.70` = **0.545** < 0.6. Convergence still occurs, one step later. |

One narrative sentence was corrected to match its own step table.
`docs/engineering-review-dataset.md` was brought into exact agreement with the
revised dataset (verified programmatically) and now records the provenance
split; its "cannot drift" claim would otherwise have become false.

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

**Why this is governance, not implementation.** Flipping `down` to `up` changes
a documented claim about what the case demonstrates. There is a real argument
the new behaviour is *more* faithful to the stated uncertainty intent —
`scoring.py` says "two strongly-supported rivals (genuine competition) → HIGHER
uncertainty", and step 3 creates exactly that near-tie — which is precisely why
it is not ours to decide. Left unchanged, so the test still fails and the
question stays visible. The case's stated **purpose** — competing candidates
rather than a single default — is unaffected and still holds.

---

## 5. Classification of all 28 pre-existing failures

M = mechanical identifier · A1 = R6 numeric · A2 = R6 threshold-discrete ·
D = other approved rule · B = needs governance · U = unexplained (defect)

| # | Test | Class | Cause | Disposition |
|---|---|---|---|---|
| 1 | `test_review_dataset[competing-resolve]` | A2 | prediction one step later | revised dataset |
| 2 | `test_review_dataset[oscillating-evidence]` | A2 | steps 2–4 predictions | revised dataset |
| 3 | `test_review_dataset[high-uncertainty-converges]` | A2 | step 2 predictions | revised dataset |
| 4 | `test_review_dataset[failed-acquisition]` | **B** | uncertainty direction flip | **OPEN — referred** |
| 5 | `test_failed_acquisition_yields_multiple_candidates` | M | authored ids | resolved via attribution; also asserts 3 lineages |
| 6 | `test_expected_vs_actual_all_match_for_dataset_case` | **D** | panel compared authored vs durable ids | **product fix** (§6) |
| 7 | `test_reasoning_unchanged_and_expectations_persist_on_save` | **D** | same | product fix |
| 8 | `test_uncertainty_series_from_timeline` | A1 | R6 offset | values recomputed; monotonic fall re-asserted |
| 9 | `test_hypothesis_evolution_series` | M + A1 | ids + opening support | translated; 0.35 / 0.15 derived |
| 10 | `test_prediction_lifecycle_events` | M | authored ids | translated |
| 11 | `test_add_does_not_run_until_run_next` | M | authored ids | translated |
| 12 | `test_add_and_run_sequence_consolidates` | M | authored ids | translated (support 0.626 ≥ 0.6, prediction still forms) |
| 13 | `test_new_and_switch_test_cases_are_isolated` | M | authored ids | translated |
| 14 | `test_trace_graph_reflect_test_case_reference_is_canonical` | M | authored ids | **discriminator changed to statements** (see §6) |
| 15 | `test_live_server_sqlite_backend_across_threads` | D | downstream of #6 | fixed by product fix |
| 16–19 | `test_trace_graph_space` (4) | M | authored ids | id read back from the store (backend-agnostic) |
| 20 | `test_reasoning_summary_generated_from_state` | M | authored ids | translated |
| 21 | `test_explain_why_from_state` | M + A1 | ids + 0.87→0.86 | translated; value derived |
| 22 | `test_review_result_pass_for_dataset_case` | A2 | downstream of dataset | fixed by revised dataset |
| 23 | `test_original_duplicate_id_failure_reproduced` | **D** | collision now caught pre-write as a governed outcome | expectation retyped; also asserts nothing was written |
| 24 | `test_durable_sqlite_defaults_to_collision_safe_ids…` | **D** | test double could not resolve its own reference | fixed in the double via documented `catalogue` |
| 25 | `test_two_subjects_same_space_are_isolated` | M | authored ids | now asserts **disjoint** id sets — stronger |
| 26 | `test_trace_is_generated_from_real_engine_state` | A1 | 0.380→0.370, 0.308→0.415 → 0.292→0.425 | values derived; fall-then-rise re-asserted |
| 27 | `test_graph_reflects_real_engine_lineage` | M + A1 | node id + support series | node identified by the **lineage claim** itself |
| 28 | `test_proposal_trajectory_hint_flows_into_prediction` | **B** | Case B, R6 threshold | **OPEN — referred** |

**No B or U failure was silently changed. No U failures were found** — every
failure resolved to an approved rule or to a defect with an identified cause.

---

## 6. Changes to product code (not test code)

Two, both stated explicitly because they are not test-only:

1. **`CandidateProposal.predicted_trajectory` restored** (errata E-1, §3).
2. **`TestCase.authored_to_durable()`** — the Expected vs Actual panel compared
   authored hypothesis ids against engine-issued ids, so it reported a mismatch
   on **every** dataset case for a reason unrelated to the reasoning under
   review. The panel runs after identity adjudication, so it must translate
   before it compares. Matching is on the **statement** — the one thing both
   sides author, the same basis `ScriptedAppraiser` already uses, and the only
   basis that works on the SQLite backend, which carries no lineage stores. A
   statement authored by more than one proposal is left **unmapped rather than
   guessed**; an unmapped id stays authored and compares unequal, which is
   visible rather than silently wrong.

   This restores the panel's existing semantics under engine-issued identity.
   No panel, field or output shape changed.

One test needed a **different discriminator** rather than a translation.
`test_trace_graph_reflect_test_case_reference_is_canonical` contrasted a test
case's trace against the canonical reference using authored ids, which were
globally unique. Durable ids are issued per subject in sequence, so both traces
now contain `hyp-1` and `hyp-2` — an id-based contrast would have **silently
proved nothing**. It now contrasts the authored statements.

---

## 7. Test results

| Suite | Result |
|---|---|
| **Phase 0 exit gate** | **8 / 8 conditions pass** |
| Root (`tests/`) | **281 passed, 2 failed** |
| Phase 1 (`sanuvia-phase1/tests/`) | **152 passed, 0 failed** |
| Semantic-state suites | 76 passed |

The two root failures are items 4 and 28 — **both classification B, both held
open deliberately.** No test was weakened, skipped, deleted or softened to
reach green, and no threshold, fixture or engine behaviour was changed to make
a test pass.

Mutation protections from Slice 1 remain in force, including the R1a
stance-inversion guard and the `commit_plan` sole-writer assertions.

---

## 8. Repository-repair evidence (verified against base `9883e6c`)

An earlier `git add -A` wrongly staged 35 Run 001/002 evidence files. The
repair is independently verified:

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

Nothing was ever pushed before the repair, so it stayed entirely local. File
contents on disk were never modified — `git add` changes only the index.

---

## 9. Boundaries honoured

Not done, as instructed: Case 002 not accessed or used; Run 003 not prepared or
executed; Run 002 evidence not modified; Case 001 not rerun or tuned; model,
provider and prompts unchanged; no retries; no repair/normalisation logic; no
frontend or product redesign; no new identity heuristics; Architecture v0.2
unchanged; Technical Design v1.5.4 unchanged beyond the authorized trajectory
clarification, which is a separate addendum; branch not merged, not frozen, not
deployed.

---

## 10. Open items for governance

1. **`dataset-failed-acquisition` step 3 uncertainty trend** — authored `down`,
   observed `up` (0.400 → 0.472). Derivation in §4.
2. **`test_proposal_trajectory_hint_flows_into_prediction`** — under R6 a single
   0.8-reliability observation yields 0.400, below the unchanged 0.600
   threshold, so no prediction forms. Derivation in §3.

Both are recorded, both still fail, neither was changed.

A third item is noted for completeness rather than decision: `REFINE_EXISTING`
remains unreachable, because the R1 model-assisted resolver is Slice 2. With no
resolver configured, a plausible-but-inexact candidate parks as
`AMBIGUOUS_REVIEW_REQUIRED` rather than committing on an unmade judgement,
exactly as §2 G specifies.
