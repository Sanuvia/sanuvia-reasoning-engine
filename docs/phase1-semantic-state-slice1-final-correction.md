# Phase 1 Semantic State — Final Bounded Slice 1 Correction

**Branch:** `phase1-semantic-state-v1.5.4`
**Corrected from:** `0c5c60b80947684245280f415f050fac5dcdc403`
**Base:** `9883e6c37328a96fcf58d9c59786b4dee4f657e1`
**Date:** 2026-10-06
**Status:** evidence for verification. **Full Slice 1 acceptance is not claimed here.**

---

## 1. Correction summary

**R2-1 — the raw appraiser response was missing from the `REJECTED_PLAN` audit
record for the unknown-reference family of rejections.**

**Cause, confirmed.** Steps 6 and 8 reject through `HandleTable`
(`resolve_hypothesis`, `resolve_participant`), which has no access to the
appraisal response, so those rejections carried no `raw_response`. The
`AppraisedObservation` that would have held it is appended only after both
steps succeed, so on rejection it was never recorded at all. `capture.py` then
wrote `rejection.raw_response or ""`, producing `raw=''`.

**Correction.** The appraisal response is recorded immediately after the call
returns. Steps 6–8 are wrapped so a `GovernedRejection` raised there is
re-raised with the response attached. Nothing else moved.

* No step was reordered and no mutation ordering changed.
* No second transaction mechanism; `commit_plan` untouched.
* Identity adjudication, the resolver, support/uncertainty, trajectory
  precedence, thresholds and the model schema are untouched.
* No retries, repair, normalisation or inference.
* The re-raise reproduces outcome, discriminators and references exactly, so
  **what is rejected and why is unchanged** — only what the audit can show.

**Multi-record interactions.** A single `raw_response` field cannot represent
an interaction that makes several appraisal calls: a rejection on a later
record would discard the responses already collected for the earlier ones.
`GovernedRejection.appraisal_responses` and
`TrajectoryRecord.appraisal_responses` carry
`((evidence_id, raw_response), ...)` — ordered by call and attributed to the
observation each answered. This reuses the existing record contract;
`TrajectoryRecord.raw` remains a canonical-JSON echo, as on every other
record, and now embeds the same ordered list.

**Reasoning-state rollback is unchanged.** The audit gained data; the state
path did not. Tests assert that a multi-record rejection whose *earlier*
appraisal succeeded still leaves no evidence, hypotheses or lineages.

## 2. Files changed

| File | Change |
|---|---|
| `src/sanuvia/domain/errors.py` | `GovernedRejection.appraisal_responses`; audit-only note |
| `src/sanuvia/application/reasoning/model_revision.py` | record the response after the call; wrap steps 6–8; `_with_appraisal_audit`; `raw_responses` collector |
| `sanuvia-phase1/src/sanuvia_phase1/trajectory.py` | `TrajectoryRecord.appraisal_responses` |
| `sanuvia-phase1/src/sanuvia_phase1/capture.py` | `from_rejected_plan` echoes the ordered responses into `raw` and surfaces them structurally |
| `docs/…-slice-allocation.md` | Slice 2 entry conditions (§5.3, §5.4) |
| `docs/…-repair-round2-reconciliation.md` | voice label ratification, check 7 / 9(a) overlap, entry conditions |

## 3. Tests added and changed

**Added — `sanuvia-phase1/tests/phase1/test_rejected_plan_raw_response.py` (13)**

Test A, single-record: `…preserves_the_raw_appraiser_response`,
`…keeps_the_governed_shape`, `…keeps_the_admitted_observations`,
`…still_rolls_reasoning_state_back`, `…raw_echo_embeds_the_response`.

Test B, multi-record: `…is_a_rejected_plan`,
`…retains_the_earlier_response`, `…retains_the_failing_response`,
`…ordered_and_attributable`, `…is_deterministic`,
`…still_rolls_reasoning_state_back`.

Negative controls: a committed interaction and a `NO_EVIDENCE_HOLD` both
record **no** appraisal responses, so the carrier is the rejected-plan audit
rather than a general response log.

**Added — `sanuvia-phase1/tests/phase1/test_resolver_wiring_guard.py` (6)**

External branch gets `identity_resolver is None` and keeps its injected real
appraiser; scripted branch gets the `ScriptedIdentityResolver`; the two are
asserted **as a pair** so neither can be cross-wired; the real-run pipeline
module is asserted to have no reachable reference to the fixture double; and
`build_in_memory_dependencies` defaults no resolver in.

**Changed — `sanuvia-phase1/tests/phase1/test_adapter_parity_td19.py`**

The assertion `scripted.raw_response == external.raw_response is None` was
asserting the defect as parity. Replaced by
`test_td19_raw_response_is_excluded_from_parity_and_preserved_per_path`:
Scripted `None` by construction, External equal to the fake client's **exact**
reply, and both interaction-level carriers asserted. Every other parity
assertion — classification, outcome, breach, boundary, committed status,
counters, reasoning-state equivalence — is unchanged and unweakened.

## 4. Raw-response behaviour by path

| Path | `raw_response` | `appraisal_responses` |
|---|---|---|
| Scripted | `None` by construction | `(("evidence-1", None),)` |
| External | the client's exact reply | `(("evidence-1", "<exact reply>"),)` |

Reproduced at the trajectory boundary: `outcome=REJECTED_PLAN`,
`governed_failure=UNKNOWN_HYPOTHESIS_REFERENCE`, `committed=False`,
`ingested_evidence_ids=('ER-001',)`, and `appraisal_responses` carrying the
exact reply — previously `raw=''`.

**Multi-record:** two calls, first succeeding and second rejecting →
`(("evidence-1", "<first reply>"), ("evidence-2", "<unknown-handle reply>"))`.
Both retained, ordered, attributed; reasoning state still fully rolled back.

## 5. Resolver guard result

External branch: `identity_resolver is None`. Scripted branch:
`ScriptedIdentityResolver`. Pairing asserted in both directions. No production
behaviour changed — the guard was already structural and no wiring defect was
found.

## 6. Carried-forward record items

* **`Sanuvia working reading`** — ratified by Lillian's reconciliation, not an
  implementation inference. Code unchanged.
* **Check 7 / 9(a)** — cross-interaction role reuse →
  `SOURCE_REFERENCE_MAPPING_FAILURE`; within one batch →
  `ACCOUNT_ROLE_UPGRADE_VIOLATION`. Intentional overlap, not an unprotected gap.
* **Divergence + `space_kind`** — Slice 2 entry condition: they land together.
  Divergence is not implemented or wired here.
* **Extractor-supplied `EvidenceStanding`** — Run 003 prerequisite. Phase 1
  extraction does not populate it, so the role gate is not live on the real
  extraction path and `RESPONSE_OR_RESONANCE` must not be treated as safely
  appraisable as ordinary support until the bounded extension lands. Not
  implemented here.

## 7. Non-blocking items not done

N-1 Scripted resolver fidelity (explicitly non-blocking; not required by any
test added here), G-2 broader 15-store parity coverage, N-3 F-2 wording. N-2
stale docstring was corrected only where directly adjacent to the touched
record.

## 8. Test results

| Suite | Before | After |
|---|---|---|
| Root | 338 passed | **338 passed** |
| Phase 1 | 178 passed | **198 passed** |
| Phase 0 exit gate | 8/8 | **8/8** |

Phase 1 grew by 20: 13 rejected-plan tests, 6 resolver-guard tests, and one
from splitting the incorrect TD-19 raw-response assertion into its own test.
No root test changed. Nothing was skipped, xfailed, deleted, relaxed or
weakened.

## 9. Protected material

| Item | Status |
|---|---|
| Original review dataset | byte-identical, `2acca2920c0a213c213abe355a171294e5a69ffa40e4b0324d21f521383fc17d` |
| `local_run001` / `local_run002` vs base | 0 tracked diffs |
| Sealed Run 002 archive | verifies against its own sealed hash |
| Addendum E-1 | `a06ca426a48aa3750d5395deae202ab839d807387030e5adf5346405bed4533d`, bytes unchanged |
| Amendment A-1 | `7ce2e5ee3f3f95870f312c0a036776b37b0a2aa5387b24c62e2eefe9161bcfa3`, unchanged |
| Seven untracked evidence paths | untracked, unstaged, unmodified |
| Case 001 evidence | not rerun as a model experiment, not tuned |
| Case 002 | **not accessed** |
| Run 003 | **not prepared** |
| Architecture v0.2 / Technical Design v1.5.4 | unchanged |
| Model / provider / prompts / thresholds / frontend | unchanged |

**No model inference was run.** Every test uses a fake client or a scripted
double.

Not merged. Not frozen. Not deployed. `main` untouched.
