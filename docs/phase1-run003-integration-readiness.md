# Phase 1 — Run 003 Integration Readiness

**Branch:** `phase1-run003-integration`
**Base:** `9037322a76b716753373c6c0049b73bf7dda51da` (merge of PR #3 into `main`)
**Date:** 2026-10-11
**Status:** reviewable integration package. Not an implementation freeze, not a
Case 002 release, not a Run 003 authorization, not a deployment.

Closes the three integration prerequisites recorded at the end of the Slice 2
merge, completes the external identity resolver's wiring, and corrects one
typing defect introduced by that merge.

---

## 1. Request-scoped participant vocabulary (§2 B applied to extraction)

**The defect.** The extraction boundary asked the model for `subject` as a bare
string and checked the reply against the authorized roster afterwards. A reply
therefore *became* a canonical `ParticipantId` whenever it happened to match
one, and was refused only when no participant happened to be called that — a
membership accident, not a rule. Locked §3.1 prohibits the application from
inferring that a model-supplied string is a canonical reference.

**The correction.** `sanuvia_phase1.participants` mints
`{request_id}::P{n}` over the sorted, deduplicated roster — the identical
scheme `handles.build_table` already fixes for the appraisal boundary, and the
same guarantee the identity resolver gets from `C1`/`C2`. This is the
established scheme applied to a third boundary, not a fourth scheme invented
for it.

| Direction | What crosses |
|---|---|
| Outbound | the request's labels, and nothing else |
| Inbound | a label, resolved to a `ParticipantId` inside the application |

`ParticipantVocabulary.resolve` is the single point at which a model-supplied
string may become a canonical reference, and it may do so only by having been
offered for *that* request. Everything else is
`EVIDENCE_ROLE_VIOLATION` under ruling Q6 — the whole interaction is rejected,
the complete extraction output and the extractor provenance are preserved, and
nothing is repaired or normalised.

**Refused, each with its own test:** an unoffered label; a canonical
participant id *that is genuinely authorized*; a label minted for a different
interaction; a name lifted out of the transcript text; a non-string subject
(caught earlier, by the strict reader).

**Prompt/schema.** `subject` is now `participant_label|null`, so the extraction
prompt and schema are bumped `v2 → v3` rather than edited in place — the
convention the appraisal schema already set, so Run 002's
`extraction.observations.v2` reference keeps meaning what it meant.
Consequently the governance freeze record moves to
`7.0-extraction-schema-v3-participant-labels`; the prior pinned hash is
preserved in `FREEZE_RECORD_HISTORY`, never overwritten.

**Reading recorded.** "Pass only the labels needed by the extractor" is
implemented as *the whole authorized roster for that request*. Any authorized
participant may legitimately be the subject of an observation, so a narrower
set would make a correct extraction unrepresentable. If a narrower per-request
set is intended, that is a governance decision and is not taken here.

---

## 2. Governed speaker context

Already correct in `complete_standing`; what was missing was proof. No code
path changed here beyond the vocabulary substitution.

* A recorded speaker arrives as a **canonical id** from the application and is
  checked for roster membership. The asymmetry with `subject` is deliberate and
  asserted: a speaker supplied as a *label* is refused, so the two namespaces
  cannot blur.
* An unauthorized speaker rejects the interaction.
* A speakerless turn is **not a failure and not an inference**. It stands as
  `SYSTEM_SURFACE`, and no speaker is derived from the roster, from the subject,
  or from the text.

**Divergence eligibility.** `EvidenceStanding.is_participant_account` requires
`role=ACCOUNT` *and* `source_kind=PARTICIPANT` *and* a non-null `source_id`, so
a `SYSTEM_SURFACE` record fails §2 J.1 rules 2 and 3 and the candidate set is
empty. Asserted end to end through the frozen engine on the exact shape that
normally *does* produce a candidate — two accounts, one subject, one shared
space — together with a **control** proving the set is non-empty when the only
difference is that both turns have speakers. Without that control the empty-set
assertion could have passed because divergence never fires at all.

Mixed pairs (speakerless + speaking, in either order) are also empty:
eligibility is a property of both endpoints.

---

## 3. REAL-mode configuration failure

`RealRunConfig` gains `participants` (the authorized roster) and
`identity_resolution` (the R1 boundary's `ModelSpec`, optional because R1 is
opt-in). `validate_run_configuration` refuses, before anything executes:

* an empty `RealRunConfig.participants`;
* an extractor built with no roster;
* a roster **mismatch** between the config and the extractor — worse than a
  missing one, because the run would look configured while extracting under a
  different vocabulary;
* a `ScriptedIdentityResolver` in REAL, or a real resolver in GOLDEN;
* a configured resolver with no `identity_resolution` spec.

Order is not part of the configuration: minting sorts, so a roster stated in a
different order is accepted.

`qwen_real_run_config()` takes `participants` and **defaults to empty on
purpose**. Who is authorized is a property of the case under evaluation, not of
the model configuration, so this function will not invent one. `preflight-real`
therefore reports the unconfigured roster as a stated `BLOCKED` prerequisite,
and its representative extractor is now built from the config's own roster —
an extractor built empty would have passed a guard the real run's extractor
then fails, which is the opposite of what a preflight is for.

---

## 4. External identity resolver wiring

`test_r1_identity_resolver` proved the *adapter* against a hand-built
dependency bundle. Nothing constructed an `ExternalIdentityResolver` through
`SanuviaPersistentCondition` or `run_transcript_demonstration`, so the real
path could only ever reach §2 G case 4 with `resolver=None` and park.

`SanuviaPersistentCondition` now takes `identity_resolver`, and
`run_transcript_demonstration` passes it through. The G-1 pairing is preserved
and now refused at **condition initialization** rather than left structural:

| Branch | Appraiser | Resolver |
|---|---|---|
| scripted / golden | `ScriptedAppraiser` | fixture-authored double, injected one **refused** |
| real | injected | the configured one, or `None` |

`None` on the real branch remains a **valid** configuration, not a degraded
one: §2 G parks a non-exact candidate rather than guessing.

**Traced end to end** with a fake client: the resolver is reached exactly once
for the one non-exact candidate (interaction 1 founds its lineage at case 3 and
consults nobody); it receives the candidate statement and the resolution-scoped
`C1` only, with no durable `HypothesisId` anywhere in the prompt;
`REFINE_EXISTING` appends a statement version without founding a lineage;
`AMBIGUOUS_REVIEW_REQUIRED` parks; `DISTINCT_NEW` founds a second lineage.

**Rejections stay governed.** Malformed output, an outcome outside the
vocabulary, an unoffered ref, and both shape rules each produce
`INVALID_APPRAISAL_RESPONSE` with `boundary=IDENTITY_RESOLVER`, carrying
`resolver_id`, `prompt_version` and `schema_version`, with the raw reply kept
in `boundary_raw_response` so a resolver failure never overwrites what the
appraiser returned.

**Rollback** is asserted over the whole bundle (enumerated, not sampled, so a
store added later is covered) *and* over the identifier counters: a third
interaction after a rejected one is issued `evidence-2`, not `evidence-3`. A
store-only atomicity check cannot see that gap.

---

## 5. Typing correction

`SnapshotableStore` lost its `@runtime_checkable` when the three semantic-state
Protocols were inserted above it; the insertion consumed the decorator and left
a duplicate on `HypothesisLineageStore`. Both corrected, and the misplaced
section header moved back above `SnapshotableStore`.

**Not a live defect.** `UnitOfWork.begin` duck-types `getattr(store, "snapshot")`
rather than asking the Protocol, so rollback was never affected — which is
exactly why it was invisible. `tests/test_store_protocols.py` now asks
directly; it fails on the pre-fix file and passes after.

---

## 6. Remaining prerequisites for Run 003

Integration-side work is complete. What remains is **configuration and
governance**, not implementation:

1. **State the authorized participant roster for the case under evaluation.**
   `qwen_real_run_config(participants=...)` and the extractor must receive the
   same roster; the guard refuses a mismatch. Case 001 is a single-subject,
   speakerless transcript, so it establishes no roster — one has to be supplied
   or the case has to be one that carries participants.
2. **Decide whether R1 runs.** `None` parks non-exact candidates and is valid.
   If a resolver is configured it needs its `RealRunConfig.identity_resolution`
   spec, which is governance-pinned like every other boundary.
3. **Approve the provider/model for extraction, appraisal and (if used)
   identity resolution.** Still unresolved; no provider is auto-selected
   anywhere, and both `*_from_env` factories refuse by design.
4. **Re-run `preflight-real` against the stated configuration** and confirm
   `OVERALL: PASS`, including the local artifact and runtime identities.

Case 002 remains sealed and was neither accessed nor inspected. No model
inference was run; every test in this package uses fake clients.
