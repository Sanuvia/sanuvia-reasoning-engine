# Phase 1 Semantic State v1.5.4 — Bounded Repair, Round 2

**Branch:** `phase1-semantic-state-v1.5.4`
**Re-reviewed commit:** `f522923c92bea61891eac545c0dadae62cdeae3a`
**Base:** `9883e6c37328a96fcf58d9c59786b4dee4f657e1`
**Date:** 2026-10-05
**Status:** read-only review. Not merged, not frozen, not deployed.

> **Reading A is confirmed and implemented.** `attribution` is the governed
> voice label on **both** adapters. Exact matches attach; plausible non-exact
> candidates **park** when no resolver is configured; nothing defaults to
> `DISTINCT_NEW`. **R1 is not implemented.**
>
> The **real External path parks non-exact candidates**, and will until R1
> lands. Identity there is engine-owned for exact matches and undecided but
> preserved otherwise.
>
> Dataset closure below concerns **dataset expectations only**. It does not
> imply identity-system completion. See
> [the slice allocation](phase1-semantic-state-slice-allocation.md).

---

## 1. Repair commits

| Commit | Scope |
|---|---|
| `6cd3127` | E-1 bytes committed; protected-evidence manifest; dataset class A2→A1 |
| `2011d62` | Reading A; attribution → voice label; Scripted resolver; M-2 store + check 10; subject-leak fix |
| `4fe7a0f` | Signature across the model boundary, both directions |
| `a7339de` | TD-18 at the trajectory boundary; TD-19 completion |
| `1158055` | Addendum E-1 Amendment A-1, trajectory precedence |

## 2. Disposition of every review item

**CLOSED** · **PARTIAL** · **OPEN** · **DEFERRED** · **NEW**

| ID | Finding | Was | Now | Evidence |
|---|---|---|---|---|
| **B-1 / M-1.1** | Model label decides durable identity via `attribution` | OPEN | **CLOSED** | Both adapters return `VOICE_SANUVIA_WORKING_READING`. Identical statements under different response-local refs now resolve to one lineage. |
| **B-2** | Retired fields prompted/required | PARTIAL | **CLOSED** | Retired fields rejected (not ignored); signature now in the schema both ways — see M-1.2. |
| **M-1.2** | Signature absent from the model-facing schema | OPEN | **CLOSED** | `HypothesisPromptView` carries subject/attribution/claim_class/stance/temporal_scope outbound; schema v3 carries `signature` inbound, validated against the governed enums. |
| **M-1.3** | Wrong subject; hard-coded class/stance | PARTIAL + **NEW** leak | **CLOSED** | Class/stance/scope from the current `StatementVersion`. Subject projected through the **inverse** participant map; lineage subject added to the request's participant set when absent. Tests reject durable-ID leakage explicitly. |
| **M-1.4** | Scripted/External parity | PARTIAL | **CLOSED** | All four required tests present, including same-content-different-refs → one lineage. |
| **M-2** | One lineage per bound | PARTIAL | **CLOSED** | Adjudicator, `_committed_views`, in-flight set, **store `_by_key`** and **check 10** all plural. `find_by_key` returns every admitted lineage; snapshot copies inner lists. |
| **M-3** | Hold writes orphan lineage/version | CLOSED | **CLOSED** | Unchanged. |
| **M-4** | Check 7 vacuous | CLOSED | **CLOSED** | Unchanged. 9 / 8a / 8b remain **DEFERRED** and are not counted. |
| **M-5** | Silent rollback downgrade | CLOSED | **CLOSED** | Noted: if a semantic store is ever added to the SQLite bundle the guard flips from "excluded" to "must have rollback" — correct, and now recorded. |
| **M-6** | `uuid4` request ids | CLOSED | **CLOSED** | Unchanged. |
| **M-7 / TD-17, 17b, W1** | Integrity coverage | CLOSED | **CLOSED** | Unchanged. |
| **M-7 / TD-18** | Service boundary only | PARTIAL | **CLOSED** | Now at the trajectory boundary — see §4. |
| **M-7 / TD-19** | Outcome parity only | PARTIAL | **CLOSED** | Classification, result shape, full state equivalence, counters — see §5. |
| **m-5** | Exit runner split `attribution` | CLOSED w/ coupling | **CLOSED** | Re-derived from the authored **statement**. No call site splits `attribution` anywhere. |
| **m-3** | Trajectory precedence undocumented | OPEN | **CLOSED** | Amendment A-1 — see §6. |
| **Dataset F-1** | failed-acquisition step 3 | CLOSED, class disputed | **CLOSED** | Reclassified **A1**: the value moves continuously, no threshold is crossed. Values and scoring unchanged. |
| **Dataset F-2** | trajectory test | CLOSED w/ nit | **CLOSED** | Nit stands as a wording matter; the companion test carries the port claim. |
| **E-1** | Cited, not supplied | OPEN | **CLOSED** | Committed at `docs/addenda/`, hash verified. |
| **Protected evidence** | `??` only attests "unstaged" | OPEN | **CLOSED** | SHA-256 manifest + sealed-archive cross-check — see §7. |
| **R1 / Slice 2** | — | DEFERRED | **DEFERRED** | Not implemented, not stubbed in any real path. |

## 3. Reading A — confirmed and implemented

The texts are consistent and they say Reading A. Architecture §3.4's
burden-of-distinctness rule forbids resolving a non-exact candidate by
automatic creation: that would declare every non-exact statement distinct
without comparison, which is the Run 002 mechanism.

Implemented exactly:

| Case | Behaviour |
|---|---|
| Exact normalised match | attaches to the existing lineage |
| Empty bound | `DISTINCT_NEW` |
| Populated bound, no exact match, **no resolver** | **parks** `AMBIGUOUS_REVIEW_REQUIRED` |
| Populated bound, no exact match, resolver present | resolver decides |

`test_distinct_statement_parks_when_no_resolver_is_configured` asserts the
park; `test_distinct_lineages_coexist_when_the_resolver_authors_distinct_new`
asserts plurality **only** via an explicitly authored decision.

### Scripted resolver — test-only, fixture-authored, Run-003-guarded

`ScriptedIdentityResolver` returns the decision a fixture **authored**. It
compares nothing: no statement comparison, no similarity, no attribution
parsing, no identifier inference. A reference the fixture never authored
parks. Every decision is recorded in `decisions_made`.

Wired into the exit-test fixture, HTTP harness / review dataset runner, the
Phase 1 **scripted** condition, the demo, and scripted test helpers.
`deps.identity_resolver` defaults to `None`. In the Phase 1 condition the
guard is **structural** — the resolver is bound to the same branch that
selects the scripted appraiser, so an injected real appraiser never receives
one.

Authored→durable mappings are derived from the authored **statement**, matched
exactly. **No code anywhere splits `attribution`.**

## 4. TD-18 at the trajectory boundary

`TrajectoryRecord` gains `outcome`, `governed_failure`, `committed`.
`InteractionOutcome` distinguishes `COMMITTED`, `HELD`, `NO_EVIDENCE_HOLD`,
`REJECTED_PLAN`. `capture.from_rejected_plan` builds the §5.8 shape;
`SanuviaPersistentCondition.step` records a refusal instead of propagating it.

Both halves asserted: rejected **state** does not survive (evidence,
hypotheses, lineages all empty); the record that the **interaction** happened
does. And the two shapes are asserted **structurally** distinct — a hold
carries no observations because none were admitted; a rejected plan carries
them because they were.

## 5. TD-19 completion

Added to outcome parity and non-persistence: offending-reference
**classification** (N-4) via the handle table's own classifier, both agreeing
`never-issued`; result shape (`outcome`, `breach_kind`, `boundary`,
`raw_response`); **complete** reasoning-state equivalence enumerated over every
store in the bundle rather than two; evidence / lineage / statement-version /
ledger explicitly; and identifier counters.

## 6. Addendum E-1 and Amendment A-1

| Document | SHA-256 |
|---|---|
| Addendum E-1 (bytes **unchanged**) | `a06ca426a48aa3750d5395deae202ab839d807387030e5adf5346405bed4533d` |
| Amendment A-1 (new) | `7ce2e5ee3f3f95870f312c0a036776b37b0a2aa5387b24c62e2eefe9161bcfa3` |

* **A-1.2 across interactions** — a new hint replaces the prior trajectory;
  absent a new hint the prior carries forward. Verified against base `9883e6c`
  as pre-existing; **no code changed**. The inaccurate comment is corrected.
* **A-1.3 within one interaction** — deterministic **last-wins** restored
  (`setdefault` → assignment), matching base behaviour. Order is fixed, so the
  outcome is reproducible. No new lifecycle outcome is introduced.

## 7. Protected evidence

| Check | Result |
|---|---|
| Original review dataset | byte-identical, `2acca2920c0a213c213abe355a171294e5a69ffa40e4b0324d21f521383fc17d` |
| SHA-256 manifest, 36 files across all seven paths | `docs/repair-evidence/protected-evidence-manifest-2026-10-05.txt` |
| Sealed archive vs its own sealed hash | `e0b23bec92b4788e65fa6129457eba1f626de026f83362ee3d97710bd5554438`, `shasum -c` **OK** |
| `git diff 9883e6c HEAD -- local_run001 local_run002` | **0 files** |
| Three tracked Run 002 blobs vs base | identical |
| Seven paths | untracked, unstaged, unmodified, undeleted |

The sealed-archive cross-check is independent of any attestation made here:
the archive verifies against the hash sealed alongside it.

## 8. Signature migration status

Both directions complete. Outbound: `HypothesisPromptView` carries the full
signature plus the request's participant labels, without which a model cannot
state a resolvable subject. Inbound: `signature {subject, claim_class, stance,
temporal_scope}`, validated by enum value; out-of-range rejected, missing
rejected, never defaulted. `attribution` is **rejected if supplied** — the
voice is not the model's to choose. Subject validation is the engine's: the
adapter passes the label through and check 1 resolves it (§1.3, F-11).

Prompt/schema bumped v2 → v3; freeze record appended `4.0` → `5.0`:

```
appraisal.support-contradict-propose.v3  d5879923204f93ef8156bded29d7331f3070de389a7795283a72b7e7f50bc93c
schema.appraisal.v3                      f8567cd05b764d0b4cc139e14216736db252b6874fd1c4f3020b878099d12459
freeze 5.0-appraisal-schema-v3-signature d3e6c79f0475dd46cfd5e5629d95cc9be650eb7d28efb24ac37300280743905c
```

Model artifact, runtime build and generation parameters unchanged. **No model
inference was run**; every test uses a fake client.

## 9. Test results

| Suite | Result |
|---|---|
| **Phase 0 exit gate** | **8 / 8** |
| Root (`tests/`) | **338 passed, 0 failed** |
| Phase 1 (`sanuvia-phase1/tests/`) | **178 passed, 0 failed** |

No test was weakened, skipped, xfailed, deleted or relaxed. No threshold,
reliability, fixture reasoning value, model, provider, or frontend behaviour
was changed. Prompts changed only under the authorized signature schema
migration.

*Correction of record: commit `a7339de`'s message states "Phase 1 181 passed".
The correct figure is 178. No result changed; the message miscounted.*

## 10. Open and deferred

**Open decisions:** none outstanding from the re-review. Every item in §2 is
CLOSED or DEFERRED.

**Deferred (Slice 2), not implemented:** R1 resolver; `REFINE_EXISTING`;
`DISTINCT_NEW` for non-exact candidates; parked-candidate resolution;
prediction lifecycle governance; checks 9 / 8a / 8b wiring.

**Standing consequence to keep visible:** the real External path parks
non-exact candidates and will until R1. No Run 003 readiness is implied.

This is a bounded repair prepared for another focused independent review, not
a claim of final acceptance.


---

## 11. Items carried forward from the closure review of `0c5c60b`

### 11.1 `Sanuvia working reading` — ratified, not inferred

`VOICE_SANUVIA_WORKING_READING` is the product decision **ratified by
Lillian's bounded reconciliation**. It is not an implementation inference.

An appraiser proposes Sanuvia's working interpretation, so a model-proposed
reading carries that voice. `participant account` is reserved for a commitment
separately attributed to the participant. The adapter sets the value and
**rejects** a model-supplied `attribution`, because letting the model choose
would let it decide whether its own interpretation is the participant's own
commitment — the distinction the immutable half of the lineage key exists to
keep.

Code behaviour is unchanged by this entry; it records the authority.

### 11.2 Check 7 / check 9(a) overlap — intentional, not a gap

Role reuse of one `SourceObservationRef` is caught on both routes:

| Where | Check | Governed outcome |
|---|---|---|
| Across interactions | check 7 | `SOURCE_REFERENCE_MAPPING_FAILURE` |
| Within one batch | check 9(a) | `ACCOUNT_ROLE_UPGRADE_VIOLATION` |

The boundary is **closed on both routes**; only the outcome *name* differs
between them. This is an intentional overlap and a boundary consequence, not
an unprotected gap. Recorded so a Slice 2 reviewer does not read the
cross-interaction case as unprotected merely because check 9(a) is inert on
the real path.

### 11.3 Slice 2 entry conditions

Two conditions are recorded in
[the slice allocation](phase1-semantic-state-slice-allocation.md):

* **divergence candidate construction and `space_kind` land together** — check
  8b's disclosure test is inert today only because the engine offers no
  candidates, so disclosure is unreachable;
* **extractor-supplied `EvidenceStanding` is a Run 003 prerequisite** — Phase 1
  extraction does not populate it, so the role gate is not live on the real
  extraction path and `RESPONSE_OR_RESONANCE` must not be treated as safely
  appraisable as ordinary support until the bounded extension lands.

Neither is implemented here.
