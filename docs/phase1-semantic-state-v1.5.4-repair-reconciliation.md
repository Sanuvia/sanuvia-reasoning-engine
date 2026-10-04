# Phase 1 Semantic State v1.5.4 — Bounded Repair Reconciliation

**Branch:** `phase1-semantic-state-v1.5.4`
**Previous review commit:** `0dbbf7d7e7bd15c0fa35f559ce77a66dfecebbfc`
**Base commit:** `9883e6c37328a96fcf58d9c59786b4dee4f657e1`
**Date:** 2026-10-04
**Status:** read-only review. Not merged, not frozen, not deployed.

> **The deterministic Slice 1 foundation is implemented and tested on BOTH
> adapters — Scripted and External. R1 / Slice 2 capability remains deferred
> and is NOT implemented.** `REFINE_EXISTING` is unreachable by construction,
> and a plausible-but-inexact candidate parks rather than committing on an
> unmade judgement, as §2 G specifies for an unconfigured deployment.

---

## 1. Repair commits

| Commit | Scope |
|---|---|
| `9a5be56` | M-2 plural lineages, M-3 orphan state, M-6 request identifiers |
| `58ee441` | M-4 TD-03 source-reference mapping, M-5 rollback capability |
| `2c22e48` | 1.2 External appraisal schema migration |
| `5065ec8` | 1.3 HypothesisView signatures, M-7 integrity coverage |
| `a1d9788` | 3.1 failed-acquisition expectation, 3.2 trajectory expectation |

---

## 2. One item STOPPED and referred — B-1 / M-1.1 / M-1.4

Recorded rather than worked around, as the authorization requires.

**Exact finding.** The immutable `attribution` is derived from a
model/fixture-authored hypothesis label, so a response-local reference decides
durable lineage identity. Scripted:
`attribution = f"scripted-fixture-migration:{authored_hypothesis_id}"`.
External: `attribution = f"external-appraisal:{local_ref}"`.

**Reproduced.** Two interactions proposing the *identical* statement under
different authored ids (`H_a`, `H_b`) produce **two** lineages (`hyp-1`,
`hyp-2`), each at support 0.4, with keys
`('subject-partner', 'scripted-fixture-migration:H_a')` and `…:H_b`. The
required behaviour — identical semantic content under different response-local
references resolving to one lineage — does not hold.

**Exact authority.** Technical Design v1.5.4 §2 H defines
`attribution: str  # participant account | Sanuvia working reading` — a voice
label, immutable on the lineage, forming the retrieval bound
`(subject, attribution)` with `subject` (F-2). It is not a per-proposal
identifier.

**The conflict.** Correcting `attribution` to a voice label makes every
commitment one voice holds about one person share a single retrieval bound.
§2 G resolution order then applies: step 2 exact match, step 3 `DISTINCT_NEW`
only when the bound retrieves **nothing**, step 4 — a plausible candidate that
is not an exact match — the `IdentityResolver` port. §2 G defines the
resolver's bounded inputs as "only the plausible existing candidates the
signature bound admits", so every lineage the bound admits is a plausible
candidate, and any second distinct statement reaches step 4. With no resolver
configured — R1 is Slice 2 and explicitly out of scope here — §2 G's stated
configuration rule parks it as `AMBIGUOUS_REVIEW_REQUIRED`.

Competing hypotheses therefore become uncreatable on the deterministic-only
arm. Measured against the corrected derivation, 4 of 5 probed dataset cases
fail outright: the second proposal parks, so a later `supports=[…]` naming it
cannot resolve and the whole interaction rejects with
`UNKNOWN_HYPOTHESIS_REFERENCE`. This contradicts locked §3.4 plurality, which
§2 G itself preserves ("distinctness is judged by statement and signature, not
by count"), and it would break the competing-hypothesis cases the review
dataset exists to exercise.

**Why it is not resolved here.** Two readings of step 3 each have textual
support and they give opposite results:

* *Reading A* — "plausible" means "admitted by the signature bound". Step 4 is
  reached whenever the bound is non-empty, so a second distinct statement
  parks. This matches §2 G's bounded-inputs sentence and its unconfigured-
  deployment rule.
* *Reading B* — "plausible" is a semantic judgement the deterministic arm
  cannot make, so with no resolver nothing is plausible and a non-exact
  candidate is `DISTINCT_NEW`. This matches M-2 being required as a
  prerequisite: several lineages can only come to share a bound if a non-exact
  candidate under a populated bound can found one, which under Reading A never
  happens, leaving M-2 unreachable.

Choosing between them changes governed identity behaviour, so it is a
governance decision, not an implementation one.

**Bounded proposal (for decision, not applied).** Adopt Reading B for the
deterministic arm only: a candidate under a populated bound with no exact
match resolves `DISTINCT_NEW` while no resolver is configured, and routes to
step 4 once one is. `attribution` then becomes the governed voice label, no
model-authored value reaches the lineage key, plurality is preserved, and no
resolver or heuristic is introduced. If instead Reading A is confirmed, the
correction must wait for R1, and the authored-id attribution stays a known,
marked defect until then.

**Current state.** The defective derivation is left in place and marked at
both sites rather than given new semantics silently. M-2 — the data shape it
depends on — is complete and tested, so no further work blocks whichever
reading is confirmed.

---

## 3. Identity and adapter contract

| Item | Status | Evidence |
|---|---|---|
| **B-1 / M-1.1** immutable attribution | **DEFERRED — referred** | §2 above; marked at both adapter sites |
| **M-1.2** External schema migration | **CORRECTED** | `2c22e48` |
| **M-1.3** HypothesisView signatures | **CORRECTED** | `5065ec8` |
| **M-1.4** Scripted/External parity | **PARTIAL** | TD-19 parity CORRECTED; the duplicate-lineage element is blocked by B-1 |

### 1.2 External appraisal schema — CORRECTED

Schema migration only; prompt shape unchanged, no broader redesign.

| | v1 | v2 |
|---|---|---|
| references | `hypothesis_id` | request-scoped **handle** |
| proposal | `{hypothesis_id, statement, initial_support, supporting_evidence_ids}` | `{local_ref, statement}` |

The three retired fields are retired because none is the model's to decide:
`hypothesis_id` (engine issues durable identity, locked §3.3),
`initial_support` (R6 derives support), `supporting_evidence_ids` (support
attaches to the observation under appraisal). The validator **rejects** a
retired field rather than ignoring it — silently dropping them would let a
model keep asserting identity and support while the engine disregarded it,
hiding a schema mismatch instead of surfacing it.

Prompt id bumped rather than edited in place, so Run 002's `…v1` reference
keeps meaning what it meant:

```
appraisal.support-contradict-propose.v2
  c80603cf77c8f58d98c51730f4011d1deaf270544871987cd819859c6a70fac4
schema.appraisal.v2
  71e5cf7acb0a53d9fa86fb1c7cf666893546034fe9927e5aff9a780b900d499e
```

Governance freeze record appended, not overwritten, per its own audit rule:

```
3.0-run001-verified      3f46ef56e12c776251a223180cfbf842f228fbbcb743ff5c466f7acf45c0a2dd
4.0-appraisal-schema-v2  8cf8dd7d25588dc892211b6fdf7f8e8f74e83a718c3308e372b4af6c06dc925a
```

Model artifact, runtime build and generation parameters unchanged. **No model
inference was run.** All tests use fake clients; no provider selected, nothing
reaches a network.

### 1.3 HypothesisView signatures — CORRECTED

`subject` now reads the lineage's stored `signature_subject` instead of the
request's first participant label; `claim_class`, `stance` and
`temporal_scope` now read the **current** `StatementVersion` instead of being
hardcoded to `INTERPRETATION` / `OPEN`. The lineage-less fallback used the
durable hypothesis id as the attribution; it now uses a constant
`UNGOVERNED_ATTRIBUTION`, which cannot encode identity, and is inert on that
path because retrieval returns nothing there.

### 1.4 Scripted/External parity — PARTIAL

| Required test | Status |
|---|---|
| 1. identical content, different response-local refs → same lineage | **BLOCKED by B-1** |
| 2. attribution boundaries preserved | **BLOCKED by B-1** |
| 3. Scripted and External unknown reference → same governed outcome | **PASS** |
| 4. TD-19 adapter parity | **PASS** |

`tests/phase1/test_adapter_parity_td19.py`, fake clients only: both adapters
yield `UNKNOWN_HYPOTHESIS_REFERENCE`, neither persists anything on the
rejection, and neither decides the rejection itself — both *return* the
unresolvable reference rather than raising, keeping the control behind the
port where it has authority (§1.3, F-11).

---

## 4. Foundation integrity — M-2 … M-7

| ID | Status | Result |
|---|---|---|
| **M-2** plural lineages | CORRECTED | Both the committed projection and the in-flight set held one `LineageView` per key and **assigned** rather than appended, so each lineage discarded the one before it and a candidate exactly matching any but the last fell through to a park. Both now hold lists; exact match scans every admitted lineage; a park records **every** plausible match. The park-or-create rule is unchanged and no resolver is introduced. 8 focused tests. |
| **M-3** refused commit / orphan state | CORRECTED | A lineage and statement version are created provisionally at `DISTINCT_NEW`, before the commit policy rules. The hold path carried both into a `committed=False` plan and `commit_plan` wrote them unconditionally, leaving a lineage for a hypothesis the model does not hold and a `StatementVersion` naming a `WorldModel` version never appended. `commit_plan` now writes them only for hypotheses with a committed record. Guard placed in the sole writer so it is an invariant of the boundary, not a property of one caller. Verified load-bearing: the hold path hands `commit_plan` 1 lineage and 1 version against 0 records. Latent under the shipped commit-all policy; the regression test injects a policy that declines a hypothesize. |
| **M-4** TD-03 source references | CORRECTED | `validate_plan` defaulted `source_ref_index` to `{}`, so check 7 was structurally unable to fire. `InMemoryEvidenceStore` now carries the `SourceRefIndex` §2 A specifies (`id_for_ref` / `ref_for_id`), `core_loop` supplies it, and the index is included in snapshot/restore. |
| **M-5** rollback capability | CORRECTED | `_unit_of_work()` returned `None` silently in three ways, one an `except Exception` swallowing the governed rejection. `rollback_capability()` now reports availability and reason; a bundle carrying semantic-state stores with no boundary raises `NON_ATOMIC_REVISION_PLAN` / `COMMIT_ATOMICITY` before any identifier is allocated. §5.9 SQLite exclusion preserved and asserted. No durable transaction architecture introduced. |
| **M-6** request identifiers | CORRECTED | `uuid4()` replaced by the injected `IdGenerator` under the `req` kind. Request ids appear in handles and every governed rejection message, so allocation must be deterministic; it must also sit inside snapshot/restore (F-4, F-6). A rejected interaction now returns its request id to the pool. |
| **M-7** transaction / sole writer | CORRECTED | See §5. |

### TD-03 — checks NOT claimed as exercised

Implemented in the validator, unwired at the call site, recorded as deferred
rather than counted as passing:

| Check | State | Why |
|---|---|---|
| 9 standing rules | implemented, inert | Phase 0 records carry no `EvidenceStanding` |
| 8b disclosure | implemented, inert | `core_loop` supplies no `space_kind` |
| 8a divergence endpoints | implemented, inert | no current adapter emits divergence proposals |

Wiring these changes which interactions reject — behaviour, not mapping — so
it is outside this repair.

---

## 5. M-7 results in detail

| Requirement | Result |
|---|---|
| **TD-18** rejected-interaction audit distinction | **PASS** — the governed outcome and its references are reported to the caller, then **every** store in the bundle is asserted empty, so neither boundary can collapse into the other |
| **TD-19** Scripted/External parity | **PASS** — same governed outcome, neither persists, neither decides |
| **Mid-commit failure** | **PASS** — a write is injected to fail part-way through `commit_plan`, *after* evidence is written. Evidence, lineages, ledger and model pointer all absent afterwards; identifier counters restored. This is the evidence-first partial mutation the boundary exists to close, tested where it would occur |
| **Per-store snapshot/restore** | **PASS — all 15 stores, no skips.** Previous coverage asserted the two methods *exist*; a store can satisfy that and still return a token aliasing live structure, so restore puts back the mutated container and rollback silently does nothing. Every container each store owns is now mutated one level deep between snapshot and restore, then asserted restored. The nested write matters because the ledger is a dict of lists (F-9) |
| **Application-wide sole writer** | **PASS** — the scan covered `model_revision` only; it now covers every module under `application/`, since an alternate mutation path in any of them would bypass the commit boundary and the `UnitOfWork` with it |

---

## 6. Outstanding decision tests — both applied

### 6.1 Failed acquisition — `0.400 → 0.4725`

**Unchanged inputs:** evidence specs; reliabilities 0.7, 0.3, 0.6, 0.8;
learning rate 0.5; `aggregate_model_uncertainty = ((1-top)+rival)/2`. Only R6's
support derivation differs. No threshold changed.

```
step 2  H_topic    = 0.5 × 0.7            = 0.35
        H_avoidance, H_external = 0.5 × 0.3 = 0.15 each
        u2 = ((1 − 0.35) + 0.15) / 2        = 0.400
step 3  H_avoidance = 0.15 + 0.5×0.6×(1−0.15) = 0.405   ← overtakes H_topic 0.35
        u3 = ((1 − 0.405) + 0.35) / 2       = 0.4725    ← RISE
```

A leader change, not a drift. The rise is what the unchanged scoring function
specifies: "two strongly-supported rivals (genuine competition) → HIGHER
uncertainty". Pre-R6, the authored 0.4 starting points let H_avoidance reach
0.58 and win outright (0.41, a fall). Classification **A2**. Narrative revised
to describe the near-tie. The case's purpose is unaffected.

### 6.2 Prediction trajectory — `predictions == ()`

Retained, not deleted, skipped or xfailed. Threshold, reliability and fixture
inputs all unchanged, including the authored `initial_support=0.7`, left
visible rather than quietly removed.

**Superseded premise, documented in the test:** it was authored on the premise
that the proposal is "prediction-worthy on arrival" because 0.7 exceeded the
0.600 threshold directly. R6 retired that premise — arrival support is
`0 + 0.5 × 0.8 × (1 − 0)` = **0.400** < **0.600**.

The distinction is preserved in the assertions: the hypothesis **is** created
and its support asserted at 0.400; the threshold asserted still 0.600;
predictions asserted empty; and the authored trajectory's **kind** and
**description** both asserted on the carried proposal. Trajectory content is
carried correctly (errata E-1) and simply has nothing to attach to. The
companion test asserts the same content reaching a real prediction once R6
accumulation crosses the gate; the negative test asserts a hint cannot create
one.

---

## 7. Addendum E-1

**Located:**
`~/Desktop/Sanuvia_Phase1_Governance_Review_v1.5.4/Sanuvia-Phase1-SemanticState-v0.2-Technical-Design-v1.5.4-Addendum-E1.md`
**SHA-256:** `a06ca426a48aa3750d5395deae202ab839d807387030e5adf5346405bed4533d`
**Cited in the evidence document:** yes, and the citation matches.
**Not rewritten in this repair.** The content-only carrier clarification stands.

### Reported, not resolved — two precedence rules the addendum does not state

No new precedence semantics were introduced by this repair, but the
implementation already carries two the addendum is silent on:

1. **Within one interaction** — `_note_trajectory` uses
   `traj_hints.setdefault(hid, trajectory)`. If two candidates in one
   interaction resolve to the same lineage and both carry a trajectory, the
   **first silently wins**. The addendum states no tie-break.
2. **Across interactions** — `_regenerate_predictions` evaluates
   `run.traj_hints.get(hid) or prior_trajectory.get(hid) or <generated>`, so a
   newly authored hint **overrides** the trajectory a prior prediction
   established. The surrounding comment says a trajectory kind "once
   established for a hypothesis, carries forward across versions", which reads
   as the opposite precedence. Comment and behaviour are in tension, and the
   addendum settles neither.

Both are reported for decision rather than resolved here.

---

## 8. Phase 1 migration classification table

| # | Expectation / artifact | Original | New | Class | Authority | Reason | Unchanged inputs | Result |
|---|---|---|---|---|---|---|---|---|
| P1 | `test_output_validation` appraisal fixture | `{hypothesis_id, statement, initial_support, supporting_evidence_ids}` | `{local_ref, statement}` | **D** | §2 C | three retired fields | parser, boundary, error type | PASS |
| P2 | retired-field handling | fields accepted | each rejected as `MalformedOutputError` | **D** | §2 C | silent drop would hide a schema mismatch | — | PASS (3 params) |
| P3 | `test_real_appraiser_wiring` fake client | v1 payload | v2 payload | **M** | §2 C | schema migration | assertions, engine path | PASS |
| P4 | `test_real_appraiser_wiring` identity assertion | `!= "H_real"` | `!= "p1"` | **M** | locked §3.3 | label renamed, claim identical | the claim itself | PASS |
| P5 | `test_real_extractor_wiring` fake client | v1 payload | v2 payload | **M** | §2 C | schema migration | assertions | PASS |
| P6 | `test_prompts_registry` prompt id/hash | `…v1` / `790e63…` | `…v2` / `c80603…` | **D** | §2 C | content changed ⇒ id bumped, not hash-patched | extraction, baseline | PASS |
| P7 | `test_prompts_registry` schema id/hash | `schema.appraisal.v1` / `f36e78…` | `schema.appraisal.v2` / `71e5cf…` | **D** | §2 C | as above | — | PASS |
| P8 | `test_governance_freeze` freeze hash | `3f46ef…` | `8cf8dd…` | **D** | §2 C | freeze record follows the schema; version appended not overwritten | artifact, runtime, parameters | PASS |
| P9 | manifest / freeze-record docs | v1 ids + hashes | v2 ids + hashes | **D** | §2 C | docs track the registry | model, runtime, generation params | PASS |
| P10 | `test_adapter_parity_td19` | — | new file | **D** | TD-19 | required coverage | — | PASS (3) |

### Exit-runner migration — explicit disclosure

Not hidden in an aggregate count. `src/sanuvia/exit_test/runner.py`
(+35 / −8) gained `_durable_ids()`, and `_check_competing_hypotheses` and
`_check_predictions_revised` map authored scenario ids (`H_A`, `H_B`) to
engine-issued durable ids before asserting.

**Classification M — mechanical.** The pass conditions keep their original
meaning at full strength ("competing hypotheses are retained", "predictions
are revised as evidence changes"); only the identifier lookup changed, because
locked §3.3 made durable identity engine-issued. The gate still evaluates
**8/8** conditions and none was weakened, removed or relaxed.

**Dependency note:** `_durable_ids()` recovers the authored id by splitting the
lineage attribution — so it depends on the same authored-id-in-attribution
derivation that B-1 identifies as defective. If B-1 is corrected under the
bounded proposal in §2, this helper must be re-derived. Recorded here so the
coupling is not discovered later.

---

## 9. Protected evidence and repository state

| Check | Result |
|---|---|
| Original review dataset byte-identical | **YES** — `2acca2920c0a213c213abe355a171294e5a69ffa40e4b0324d21f521383fc17d`, 28 065 bytes, unchanged vs base |
| `git diff 9883e6c HEAD -- local_run001 local_run002` | **0 files** |
| `llama_server_backend_run002.py` | base `f3c7835e1a44` = HEAD `f3c7835e1a44` |
| `run002_case001_harness.py` | base `ff8f5cd5e2ac` = HEAD `ff8f5cd5e2ac` |
| `run002_gate1.py` | base `4cc3ae994bb2` = HEAD `4cc3ae994bb2` |
| Seven untracked evidence paths | **untracked, unstaged, unmodified, undeleted** |

Dated capture: `docs/repair-evidence/git-status-2026-10-04.txt`.

---

## 10. Test results

| Suite | Result |
|---|---|
| **Phase 0 exit gate** | **8 / 8 conditions pass** |
| Root (`tests/`) | **329 passed, 0 failed** |
| Phase 1 (`sanuvia-phase1/tests/`) | **158 passed, 0 failed** |

No test was weakened, skipped, deleted or relaxed to obtain green, and no
threshold, fixture, reliability or engine behaviour was changed to make a test
pass.

### Final classification

* **Passing governed contract tests** — all of the above. The deterministic
  Slice 1 foundation is implemented and tested on **both** adapters.
* **Remaining documented decision items** — none open in the test suites. Both
  §3 decision expectations are applied; `REFERRED_TO_GOVERNANCE` is empty.
* **Deferred Slice 2 capability** — the **R1 model-assisted identity
  resolver**. Not implemented, not stubbed, not simulated.
  `REFINE_EXISTING` is unreachable by construction and asserted so. With no
  resolver configured, a plausible-but-inexact candidate parks rather than
  committing on an unmade judgement (§2 G).
* **Implementation defects** — one open: **B-1 / M-1.1**, the authored-id
  attribution, referred to governance in §2 with a bounded proposal. It is
  marked at both adapter sites and is not worked around. Its prerequisite
  (M-2) is complete, so no further work blocks either resolution.
* **Checks implemented but not exercised** — standing rules (check 9),
  disclosure (check 8b), divergence endpoints (check 8a), recorded in §4 and
  not counted as passing.
