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

## 8. Bounded repair — independent review of 2026-10-07

Three blockers, each reproduced before the fix and each regression driven
through the real caller path.

### B-1 — closed resolver reference vocabulary

**Defect reproduced.** The request offered only `C1`. A reply naming `hyp-1`
was carried forward **as the durable `HypothesisId`** and accepted, attaching
`evidence-2` to the existing lineage. `hyp-9` was refused only because no such
lineage existed — a store-membership accident, not a rule.

**Repair.** `matched_ref` is validated against the offered reference set
before any mapping. An unoffered label is unusable output, never interpreted
as a durable identifier. The docstring claiming an unknown label is "returned
as-is so the application rejects it" is removed; it described the defect.

### B-2 — governed resolver rejection with complete provenance

**Defect reproduced.** A `"not json"` reply escaped as `MalformedOutputError`.
Rollback happened, but no governed rejected-plan record was ever produced.

**Repair.** `ExternalIdentityResolver.resolve` converts the validation failure
into `INVALID_APPRAISAL_RESPONSE` with `boundary=IDENTITY_RESOLVER`, carrying
the exact raw reply and the resolver provenance. No retry, no repair, no
normalisation, no fallback outcome.

`GovernedRejection` gained `provenance`; `TrajectoryRecord` gained `boundary`,
`boundary_raw_response` and `boundary_provenance`. The rejected-plan record
now recovers: governed failure, boundary, resolver raw response, resolver id,
prompt version, schema version, `committed=false`. The interaction's appraisal
responses are kept **separate** — both boundaries are crossed in the same
interaction and neither may overwrite the other.

Provenance coverage is stated precisely in §10, which supersedes any blanket
reading of this paragraph. At the time of the B-2 repair, several
valid-JSON-but-unusable shapes were still rejected at the application layer,
where only `resolver_id` is available, so their records carried no prompt or
schema version. A-1 closed two of them; R-1 and O-1 closed the rest.

### B-3 — interaction-level extraction rejection

**Defect reproduced.** With two turns where turn 2 proposed `role="resonance"`,
extraction aborted the **entire run**: turn 1 never reached its condition, the
validated extraction output was lost, and no interaction-level record existed.

**Repair.** `build_extracted_case` catches the governed rejection per
interaction and marks that `CaseInteraction` pre-rejected with empty evidence;
the loop continues. `SanuviaPersistentCondition.step` emits the rejected-plan
record for it. The extractor re-raises carrying the complete validated
extraction output as `raw_response`, so ruling Q6's preservation requirement
is met. Provider response and interaction rejection record remain distinct.

A test asserts that reasoning state after the two-turn run is **equivalent to
processing only the valid interaction**.

### Tests tightened, none weakened

`test_malformed_resolver_output_is_rejected_not_repaired` now requires the
governed outcome, boundary, exact raw reply and resolver id rather than
accepting either exception class.
`test_resolver_naming_an_unadmitted_lineage_is_a_governed_failure` is replaced
by `test_resolver_reference_vocabulary_is_closed`, parametrised over `C99`,
`hyp-1` and `hyp-9`, so it tests the closed vocabulary rather than relying on
durable-id membership.
`test_an_invalid_proposed_role_rejects_the_whole_interaction` now requires
`EVIDENCE_ROLE_VIOLATION` and asserts the preserved extraction output; the
empty-role case is split into a separate shape-failure assertion, because an
absent value never reaches the application's value judgement.

### Deferred — Run 003 prerequisites, recorded not implemented

Classified as Run 003 prerequisites, not blockers for this repair, and
deliberately **not** implemented here. None is Slice 2 policy:

1. **Request-scoped participant labels for the extractor**, mapped back safely.
   The extractor is currently given durable participant identifiers as the
   permitted set.
2. **Governed speaker context.** A speakerless transcript yields
   `source_kind=SYSTEM_SURFACE`, so no record is a participant account and
   divergence eligibility is empty.
3. **REAL-mode failure when the permitted-participant configuration is
   absent.** An empty permitted set currently rejects every proposed subject
   rather than failing clearly at configuration time.

## 9. A-1 — resolver shape validation at the provenance boundary

Audit-completeness follow-up to the independently accepted Slice 2 milestone.
Not a blocker, and it reopens nothing.

**Gap.** Two valid-JSON resolver shapes were rejected in
`identity.py::_govern_resolver_decision`:

* `MATCH_EXISTING` with `matched_ref = null`;
* `DISTINCT_NEW` with a non-null `matched_ref`.

Both are **shape** rules, decidable from the reply alone, not semantic identity
adjudication. Raised at the application layer, the rejection could carry only
`resolver_id` — reproduced before the repair — so the audit could not say which
prompt or schema version produced the unusable reply.

**Repair.** Both rules moved into `validate_identity_resolution`, the adapter's
validation boundary, which is where the resolver's provenance lives. The
existing `except MalformedOutputError` path there already raises the governed
failure with the full provenance, so no new failure path was introduced.

**Defence in depth retained.** The application-layer checks are unchanged and
unweakened. They are now unreachable through the normal adapter path, and a
test proves they still reject both shapes when an `IdentityDecision` is
supplied directly — the case the guard exists for.

**Result.** Both shapes now produce `INVALID_APPRAISAL_RESPONSE` with
`boundary=IDENTITY_RESOLVER`, the exact raw reply, and `resolver_id`,
`prompt_version` and `schema_version`, with reasoning state unchanged and no
identifier consumed.

**Not changed:** B-1 closed vocabulary, B-2 malformed-output handling, B-3
interaction-level extraction rejection, the four identity outcomes, the
resolver protocol, its prompt, and every other failure's provenance semantics.

**Observed, not fixed at the time (out of the A-1 scope):** `REFINE_EXISTING`
with `matched_ref = null`. Closed by R-1 in §10.

## 10. R-1 / O-1 — the remaining resolver shapes, and verified coverage

Follow-up to A-1. Same pattern, same boundary, no new mechanism.

**R-1 — `REFINE_EXISTING` must name an offered reference.** The *presence*
rule moved into `validate_identity_resolution`; it previously rejected at the
application layer carrying only `resolver_id`. The *offered* half was already
correct: every non-null reference passes through the adapter's closed
vocabulary (B-1), so naming a durable id cannot bypass it on the refine path
any more than on the match path. Both halves are now tested.

**O-1 — `AMBIGUOUS_REVIEW_REQUIRED` must not name a reference.** This was
**accepted** before the repair, not merely under-provenanced: a reply naming
`C1` alongside an unresolved outcome passed through. It is now rejected at the
same boundary. Valid parking is unchanged and asserted.

### Verified provenance coverage

Every row below is reproduced by a test that drives the real
`ReasoningService` and the real `ExternalIdentityResolver` with a fake client.
"Complete" means `INVALID_APPRAISAL_RESPONSE`, `boundary=IDENTITY_RESOLVER`,
the exact raw reply (whitespace included), and all three of `resolver_id`,
`prompt_version`, `schema_version` — on the rejection **and** on the
rejected-plan record, with `committed=false`, all 15 stores unchanged and no
identifier consumed.

| Resolver reply | Rejected at | Provenance | Covered by |
|---|---|---|---|
| Malformed / non-JSON | adapter | **complete** | B-2 |
| Reference not offered (any outcome) | adapter (closed vocabulary) | **complete** | B-1, R-1 |
| `MATCH_EXISTING` + null ref | adapter | **complete** | A-1 |
| `DISTINCT_NEW` + ref | adapter | **complete** | A-1 |
| `REFINE_EXISTING` + null ref | adapter | **complete** | **R-1** |
| `AMBIGUOUS_REVIEW_REQUIRED` + ref | adapter | **complete** | **O-1** |

The four outcome/reference rules are exhaustive over the identity vocabulary —
one per outcome — so no resolver shape remains that is rejected without
complete provenance.

### Defence in depth

The application-layer checks are unchanged and unweakened, and are tested
against directly-supplied `IdentityDecision` objects for `MATCH_EXISTING`
without a reference, `DISTINCT_NEW` with one, and `REFINE_EXISTING` without
one.

`AMBIGUOUS_REVIEW_REQUIRED` with a reference has **no** application-layer
equivalent, and none was added.

**Correction to an earlier statement.** That absence was previously described
by saying a stray `matched_hypothesis_id` on a parked decision is "inert".
That was imprecise. It is inert *for reasoning state*: the parked
`IdentityAdjudication` builds its `plausible_matches` from the resolver's
plausible set, not from `matched_hypothesis_id`, and no lineage, hypothesis,
support value or statement version is affected by it. But
`IdentityAdjudication.decision` persists the **whole** `IdentityDecision`, so
a stray reference *was* recorded on the parked audit record. "Inert" should
have been "did not affect reasoning state, but was recorded in the audit".

This is not a live defect: O-1 now rejects the shape at the adapter, so such a
decision cannot reach the application at all. The application-layer guard
remains absent by choice — adding one would be new governed behaviour beyond
the authorised shape rules — and the adapter rule is what enforces O-1.

---

Slice 1 remains accepted. This milestone implements only the authorized Slice 2
allocation. Case 002 remains sealed and withheld. Run 003 execution, merge,
implementation freeze and deployment remain separately authorized.
