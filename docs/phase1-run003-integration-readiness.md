# Phase 1 — Run 003 Integration Readiness

**Branch:** `phase1-run003-integration`, then `phase1-qwen-prompt-boundary`
**Base:** `9037322a76b716753373c6c0049b73bf7dda51da` (merge of PR #3 into `main`)
**Integration merged at:** `8e680c2d64493675c9a7dabe70c1dfba888a3604` (PR #4)
**Date:** 2026-10-11
**Status:** reviewable integration package. Not an implementation freeze, not a
Case 002 release, not a Run 003 authorization, not a deployment.

> **Amended 2026-10-24 — governance record `8.0-run003-output-cap-1536-and-chat-template-pin`,
> hash `sha256:f62c33b1dd72d623c685267cb54e5eade5bfeb41e86b9a7c556a7f5384a17bac`.** The generation row below now reads max-out `1536`;
> as recorded on 2026-10-11 it read `512`. Nothing else changed.

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

## 6. Qwen prompt boundary (follow-up to PR #4)

PR #4 landed the vocabulary but left it stranded at the last step:
`compose_extraction_prompt` assembled the Qwen prompt from `system`,
`transcript_text` and `instruction`, and **dropped
`ExtractionRequest.participants`**.

The v3 system prompt tells the model that `subject` "is one of the participant
labels given for this request". None were given. So the model was asked to name
a label it had never been shown, and every subject it proposed was refused by
the vocabulary for being unoffered — the boundary could only fail, in a way that
read as a model failure rather than a composition bug.

`compose_extraction_prompt` now renders a `PARTICIPANT LABELS:` block exactly as
`compose_appraisal_prompt` already did, so one reader sees one shape at both
boundaries. Only the labels cross: the canonical roster never reaches that
function, and validating a returned label still happens inside the application
boundary in `ParticipantVocabulary.resolve`.

**The registry hashes are unaffected.** The pinned hash covers the extraction
*system prompt*, which did not change; composition is a separate assembly step.
`verify_prompt_integrity()` reports no drift.

Regressed through the real `QwenClient` path over a fake backend, asserting on
the string `QwenBackend.generate` actually receives — not on the request object,
which was correct all along. Reverting the one-function fix fails 3 of the 11
new tests.

## 7. Configuration and approval status

### 7.1 Correction to this document

An earlier revision listed *"Approve the provider/model for extraction,
appraisal and (if used) identity resolution — still unresolved"*. That was
**wrong** for extraction, appraisal and the baselines, and is corrected here.
Those boundaries are approved and FROZEN; what is unresolved is narrower and is
stated in 7.4.

### 7.2 Approved and pinned

`is_real_run_permitted()` is `True`, with **zero** blocking governance items and
one non-blocking pending item (`eval_hardware`, recorded at run time). The
following are FROZEN, sourced to *"Phase 1 Run-001 governance approval
(2026-08-26)"* with the artifact identity verified on 2026-08-31:

| Item | Pinned value |
|---|---|
| `provider_local_only` | `local_qwen` (local only, no cloud, no API key) |
| `model_family` | `Qwen3-4B` |
| `model_artifact_version` | `Qwen/Qwen3-4B-GGUF@bc640142c66e1fdd12af0bd68f40445458f3869b :: Qwen3-4B-Q4_K_M.gguf` (2 497 280 256 bytes) |
| `artifact_sha256` | `7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5` |
| `serving_runtime_backend` | llama.cpp (GGUF) |
| `llama_cpp_build` | build 10721 (commit `8e53fcefd`), macos-x64 prebuilt release |
| `quantization` | `Q4_K_M` |
| generation | temperature `0.0`, seed `0` (fixed), max-out `1536` *(amended 2026-10-24; was `512`)*, context `8192`, stop `none`, retries `0` |

Freeze record `8.0-run003-output-cap-1536-and-chat-template-pin`, hash
`f62c33b1dd72d623c685267cb54e5eade5bfeb41e86b9a7c556a7f5384a17bac` *(amended 2026-10-24; this section was recorded against
`7.0-extraction-schema-v3-participant-labels`, hash
`16c7cbad9b364b0db86b9219a6dc2f0d768ba9afb9237246d678454aa8bf371c`)*.

### 7.3 Prompt and schema versions (verified from the live registry)

| Boundary | Prompt id | Prompt SHA-256 | Schema id | Schema SHA-256 |
|---|---|---|---|---|
| Evidence extraction | `extraction.observations.v3` | `05e1a9d408d720fa87fc663d8a0a17ff7fe757f5323e74047b86c0bac74ce1a3` | `schema.extraction.v3` | `18b9b9968492e773237745d52c5d8a6ea09b5ccebe8f4007760e7baaf3320519` |
| Evidence appraisal | `appraisal.support-contradict-propose.v3` | `d5879923204f93ef8156bded29d7331f3070de389a7795283a72b7e7f50bc93c` | `schema.appraisal.v3` | `f8567cd05b764d0b4cc139e14216736db252b6874fd1c4f3020b878099d12459` |
| Both baselines (shared) | `baseline.reasoning.v1` | `3557977b65552a1a19b3cff3a53f58b93c0efb6e802b821abe0b063cf03943bc` | `schema.baseline.v1` | — |
| Identity resolution (R1) | `identity.r1.bounded.v1` | `45d0675753216e1439230776ffbf2150f82c760f04dd276b87344276415398d6` | `schema.identity.v1` | — |

`verify_prompt_integrity()` reports no drift.

### 7.4 Unresolved — for the project owner, not assumed here

1. **Does the 2026-08-26 Run-001 approval extend to Run 003 under the v3
   extraction prompt/schema?** The approval predates the v3 bump. The model,
   runtime and generation parameters are unchanged; *what the model is asked
   for* is not. This is a scope question the source records do not answer, so it
   is recorded as open rather than read either way.
2. **The R1 identity-resolution boundary carries no approval.** It postdates the
   Run-001 approval, has no governance item, and `qwen_real_run_config()` emits
   no `identity_resolution` spec. If R1 runs in Run 003 it needs its own
   provider/model/prompt/schema approval. If it does not, §2 G parks non-exact
   candidates and nothing further is required.

### 7.5 Is the REAL configuration complete?

**No — two gaps, neither of them code.**

| Check | Status |
|---|---|
| Governance blocking items | none |
| Provider / model / runtime / parameters | pinned and frozen |
| Prompt & schema integrity | no drift |
| **Authorized participant roster** | **absent** — `qwen_real_run_config()` defaults `participants` to empty by design |
| **Local model artifact** | **absent on this machine** |

Preflight run on 2026-10-11 against `qwen_real_run_config()` as it stands:

```
OVERALL: BLOCKED
  BLOCKED  no_scripted_doubles_in_real   RealRunConfig.participants is empty
  BLOCKED  model_installed_available     runtime(s) ['llama-cli','llama-server'] present
                                         but no model artifact configured/found
  BLOCKED  model_version_identifiable    model not available, version not identifiable
  BLOCKED  artifact_sha256_recorded      no installed artifact to hash (not invented)
```

With a roster supplied, `qwen_real_run_config(participants=("pA","pB"))`, the
configuration check clears and only the three environment checks remain:

```
OVERALL: BLOCKED
  BLOCKED  model_installed_available     (as above)
  BLOCKED  model_version_identifiable    (as above)
  BLOCKED  artifact_sha256_recorded      (as above)
```

Those three are environment, not governance: this machine has the llama.cpp
runtime but no `$SANUVIA_QWEN_MODEL_PATH` artifact. Nothing is invented to fill
them.

## 8. Remaining prerequisites for Run 003

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
3. **Install the approved model artifact on the run machine.** The artifact
   identity and its SHA-256 are already frozen (7.2); the file is simply not
   present here, so `$SANUVIA_QWEN_MODEL_PATH` has to point at it. No provider
   is auto-selected anywhere and both `*_from_env` factories refuse by design.
4. **Resolve the two approval-scope questions in 7.4** — whether the Run-001
   approval carries to Run 003 under the v3 extraction prompt/schema, and
   whether R1 is in scope at all. Neither is assumed here.
5. **Re-run `preflight-real` against the stated configuration** and confirm
   `OVERALL: PASS`, including the local artifact and runtime identities. As of
   2026-10-11 it is `BLOCKED` on the roster and the three artifact checks (7.5).

Case 002 remains sealed and was neither accessed nor inspected. No model
inference was run; every test in this package uses fake clients.
