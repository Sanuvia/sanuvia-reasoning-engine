# Phase 1 Semantic State — Slice 2 Milestone

**Branch:** `phase1-semantic-state-v1.5.4`
**Slice 1 accepted at:** `90f6a065f57193e07f1144dbe6bb7fe50a9eed2c`
**Base:** `9883e6c37328a96fcf58d9c59786b4dee4f657e1`
**Date:** 2026-10-06
**Status:** reviewable milestone. Not merged, not frozen, not deployed.

---

## 1. R1 — bounded model-assisted identity resolver

**Implemented.** Invoked at §2 G resolution-order case 4 only. An exact
normalised match is decided deterministically and never reaches the model —
asserted directly, so an exact duplicate costs no model call.

**Ownership boundary.** The model proposes *sameness*; the application owns
candidate membership, identity adjudication, durable identity,
revision-before-addition and commit permission. Every answer is validated
before it can take effect: the outcome must be one of the four governed
values; a named lineage must be one the bound admitted; `DISTINCT_NEW` must
name nothing; a merge outcome must name something. **No durable identifier
crosses the boundary** — candidates are presented under resolution-scoped refs
(`C1`, `C2`, …) minted in the adapter and mapped back, so a model that cannot
see a `HypothesisId` cannot assign one.

**Governed outcomes exercised:** `MATCH_EXISTING`, `REFINE_EXISTING`,
`DISTINCT_NEW`, `AMBIGUOUS_REVIEW_REQUIRED`, plus
`INVALID_APPRAISAL_RESPONSE` with `boundary=IDENTITY_RESOLVER` (F-7 d) and
`INVALID_CONTRADICTION_PLAN` on the inverted-stance `DISTINCT_NEW` path.

**R1a (C-1), narrow (D-2).** An inverted-stance **merge** outcome is discarded
and parks; `DISTINCT_NEW` and `AMBIGUOUS_REVIEW_REQUIRED` stand. The old
all-inversions-park behaviour is not reintroduced. An inverted-stance
`DISTINCT_NEW` remains subject to check 10. What the resolver returned is kept
as `overridden_resolver_outcome`, so a discard is auditable.

**`REFINE_EXISTING`** appends a `StatementVersion` and never overwrites, so a
re-presented earlier statement still identifies the lineage (F-2). `subject`
and `attribution` cannot change on this path — they are immutable, so a
re-attribution is bound to a different retrieval key and cannot reach it.

**No retries, no repair, no normalisation.** `confidence` is provenance only
(F-8): a `DISTINCT_NEW` at 0.01 still founds a lineage.

**Limitations.** The resolver is opt-in and unconfigured by default; without
it a non-exact candidate still parks (Reading A unchanged). Parked candidates
are created, preserved and reported — ruling Q2 supplies no resolution path,
and none is invented.

**Prompt/schema:** `identity.r1.bounded.v1` `45d06757…398d6`,
`schema.identity.v1` `31e731be…17e8`.

**Tests:** `sanuvia-phase1/tests/phase1/test_r1_identity_resolver.py` — **28
passed**.

## 2. Extractor-supplied evidence standing

**Implemented.** The extractor **proposes** `role`, `subject`, `subject_kind`
— only what cannot be supplied from context. The application **supplies** the
contextual facts (who spoke → `source_kind` / `source_id`; the permitted
participant set) and **validates** the proposal. A model reply that states
`source_kind`/`source_id` is rejected.

**Ownership boundary.** An invalid proposed `role` or `subject` raises
`EVIDENCE_ROLE_VIOLATION` and rejects the **whole interaction** (ruling Q6):
no repair, no normalisation, no segment-level partial commit.

**The role gate is live on the real extraction path.** Standing now flows
extractor → `ExtractedEvidence` → `CaseEvidence` → `EvidenceInput` →
`EvidenceRecord`, so `is_appraisable` has something to read. A test drives a
`RESPONSE_OR_RESONANCE` record through the engine with an appraiser that
raises if called: **no appraisal call is made**, the record is admitted and
preserved, and no hypothesis exists afterwards. That is F-1 / TD-13e enforced
structurally.

**Absent standing is left absent**, never defaulted to ordinary supporting
evidence — defaulting is exactly how resonance would acquire the power to
raise support.

**Explicitly not done.** The legacy fixture `evidence_role` vocabulary
("resonance", "decision", …) is **not** mapped onto the governed
`EvidenceRole` enum: deriving one from the other would be inventing standing
the fixture never stated. No support threshold, R6, reliability or
learning-rate behaviour was touched, and standing changes neither attribution
nor identity.

**Prompt/schema:** `extraction.observations.v2` `08d015d8…2844`,
`schema.extraction.v2` `ae54b5b1…bfab`. Freeze record
`6.0-slice2-extractor-standing` `f79197af…30bf`.

**Tests:** `sanuvia-phase1/tests/phase1/test_evidence_standing.py` — **19
passed**.

## 3. Divergence candidate construction + `space_kind`

**Implemented together, in one change**, as the entry condition required.

`space_kind_of()` derives the kind a well-formed space id declares. `core_loop`
supplies it to `validate_plan`, so check 8b's "divergence requires a shared
space" test is live rather than a no-op. In the same change, `ingest` builds
the closed candidate set — **only** where the space is `SHARED` (rule 7 at
construction), so nothing can be disclosed across a personal or undeclared
boundary.

**Governance preserved.** Divergence is `EvidenceRecord` ↔ `EvidenceRecord`,
symmetric via canonical ordering (one relationship whichever direction it was
proposed from), co-valid, separate from contradiction and off the support
axis. The approved candidate rules are used unchanged — no new eligibility
heuristic, no change to cardinality, deterministic presentation order
preserved. A repeated partner in one response is rejected as
`INVALID_DIVERGENCE_PLAN`, not silently de-duplicated.

**One behavioural consequence, stated.** A `DIVERGES_WITH` edge now survives a
hold. A divergence is evidence ↔ evidence, so it depends on no hypothesis
committing and is applied atomically with the plan; an interaction that only
records a divergence changes no WorldModel version but the relationship is
still reasoning state. Other edges are still dropped on a hold — a `SUPPORTS`
edge whose revision event did not commit would be the orphan class M-3 closed.

**Governed outcomes exercised:** `INVALID_DIVERGENCE_PLAN` (duplicate partner;
non-shared space disclosure).

**Tests:** `tests/test_slice2_divergence.py` — **18 passed**.

## 4. Prediction trajectory — preservation only

**No lifecycle policy introduced.** The accepted contract is unchanged: a new
hint replaces the prior trajectory across interactions; the prior carries
forward when no new hint is supplied; last-wins within one interaction; hints
are content-only and alter no support, uncertainty, derived state or inquiry.

Regression coverage was added because R1, standing and divergence touched
adjacent code — asserted through a resolver-wired engine, the configuration
most likely to have disturbed it.

**Tests:** 8 trajectory tests pass, including the two new regressions.

## 5. Integration / ownership

Unchanged and re-verified by the suites: `commit_plan` remains the sole
writer; reasoning-state mutation is atomic with rollback; rejected-plan audit
behaviour is preserved; handles stay request-scoped; and no durable
`ParticipantId` or `HypothesisId` reaches a model-facing representation — the
R1 adapter mints its own refs precisely so that stays true.

## 6. Test results

| Suite | Result |
|---|---|
| Root | **358 passed, 0 failed** |
| Phase 1 | **245 passed, 0 failed** |
| Phase 0 exit gate | **8 / 8** |
| R1 resolver | 28 passed |
| Evidence standing / role gates | 19 passed |
| Divergence + `space_kind` | 18 passed |
| Trajectory | 8 passed |

Baseline was Root 338 / Phase 1 198. The increases are the focused Slice 2
tests; no existing test was skipped, xfailed, deleted, relaxed or weakened.

## 7. Remaining / deferred

* **Parked-candidate resolution** — ruling Q2: parked candidates are created,
  preserved and reported; no resolution path exists and none was invented.
* **Derived state (§2 K) and inquiry validity (§2 L)** — not in this
  allocation.
* **Check 9's within-batch role-upgrade trigger** is live; the
  cross-interaction case remains covered by check 7 as
  `SOURCE_REFERENCE_MAPPING_FAILURE` — the intentional overlap recorded
  previously.
* **Run 003 readiness is a separate question** and is not claimed. The R1
  prompt/schema are registered and hash-pinned but are not added to the
  governance freeze's blocking item set; that belongs with Run 003
  preparation, which is not authorized here.
* No claim of full reasoning-system completion is made.

---

Slice 1 remains accepted. This milestone implements only the authorized Slice 2
allocation. Case 002 remains sealed and withheld. Run 003 execution, merge,
implementation freeze and deployment remain separately authorized.
