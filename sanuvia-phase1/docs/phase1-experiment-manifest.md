# Phase 1 — Experiment Manifest & Protocol (for approval)

**Status:** APPROVED (Run 001) — artifact identification pending · **Prepared:** 2026-08-23 · **Updated:** 2026-08-26
**Scope:** Sanuvia Phase 1 — Controlled Reasoning Demonstrator, first REAL run
**Companion:** [Semantic Evaluation Protocol](phase1-semantic-evaluation-protocol.md) (§10–§11) · [Governance / Freeze Record](phase1-governance-freeze-record.md)

This manifest defines the frozen experimental setup for the first real evaluation.
It is written to be pre-registered: once approved and frozen (§13), nothing here
may change after results are observed. Values that are not yet authoritatively
defined are labelled **PENDING APPROVAL** or **PROPOSED**; no thresholds or scoring
scales are invented. **The real evaluation has not been run.**

Authoritative sources: Sanuvia System Architecture v1.1; Engineering Specification
v0.4; Reasoning Semantics Specification v0.2; Implementation Programme v1.4; the
agreed Phase 1 architecture; the Phase 1 experiment protocol.

---

## 1. Experiment objective

Phase 1 tests **whether Sanuvia's longitudinal reasoning system produces a
meaningfully different reasoning trajectory** over one longitudinal case than each
of two foundation-model baselines:

- a **stateless** LLM (each interaction answered independently), and
- a **transcript-context** LLM (given the accumulated raw transcript).

This is a **whole-system comparison** (Sanuvia-as-a-system vs each baseline-as-a-
system). It **does not** establish that *persistence alone* is the causal mechanism
for any observed difference — attributing causation to a single component would
require a separate ablation/causal study, which is explicitly **out of scope** for
Phase 1. Phase 1 also does **not** establish user benefit; that is assessed
separately by human evaluation (§10).

The experiment yields (a) recorded longitudinal **observables** per condition and
(b) inputs for a **human semantic evaluation**. It does **not**, in this phase,
compute an aggregate pass/fail (see §12).

---

## 2. Conditions

Exactly three conditions, driven through the **same** ordered interaction sequence.
A fairness guard (`pipeline.run_transcript_demonstration`) enforces identical seq
labels across all three and forbids any condition altering the disclosed evidence
sequence.

| Property | **A. Sanuvia Persistent** (`sanuvia_persistent`) | **B. Stateless LLM** (`fm_stateless`) | **C. Transcript-context LLM** (`fm_transcript`) |
|---|---|---|---|
| **Input each step** | Structured evidence **extracted** from the current turn, ingested via the frozen Phase 0 public API | Raw text of the **current** interaction only | Raw text of the current interaction **plus all prior raw turns** |
| **Retained state** | Full persistent World Model across all interactions | **None** between interactions | **Raw transcript text buffer only** |
| **Unavailable state** | — | Any prior turn, any prior output, any Sanuvia structure | Any Sanuvia structure (see below) |
| **Evidence representation** | Phase 0 `EvidenceRecord`s (observations + provenance) | Raw conversation text (`turn-N: …`) | Raw conversation text (`turn-N: …`) |
| **Transcript access** | Not as hidden state — Sanuvia sees only extracted evidence, never the raw accumulated transcript | Current turn text only | Accumulated raw transcript |
| **Structured World Model** | Yes (persistent) | **No** | **No** |
| **Inquiry access** | Yes (Phase 0 `Inquiry`, status lifecycle) | No | No |
| **Hypothesis access** | Yes (Phase 0 hypotheses, support/contradiction) | Only what it re-derives this turn | Only what it re-derives from text |
| **Uncertainty access** | Yes (engine-computed World-Model uncertainty) | No structured uncertainty | No structured uncertainty |
| **Prediction access** | Yes (Phase 0 predictions/trajectories) | No | No |

**Fairness / state-separation rule (authoritative).** The baselines must **never**
receive Sanuvia's structured evidence, hypotheses, support/contradiction,
uncertainty, inquiry state, dependency/provenance graph, predictions, or World
Model. Sanuvia must **not** receive the raw accumulated transcript as hidden state.
This separation is enforced structurally: baselines run through
`StatelessFmCondition` / `TranscriptContextFmCondition` (raw-text contexts only)
and Sanuvia through `SanuviaPersistentCondition` (frozen public API only). Tests
`test_stateless_context_guarantee.py` and `test_qwen_components_manifest.py`
(`test_baselines_receive_no_sanuvia_structured_state`) assert no structured
leakage and correct stateless-isolation vs transcript-accumulation.

**Note on the appraisal boundary (Programme v1.4 Part 2).** In condition A the LLM
acts only as the **evidence appraiser** ("FM proposes candidate inferences"): it
may propose candidate hypotheses and flag support/contradiction, but the **frozen
Phase 0 engine** owns all model revision, uncertainty, inquiry, and persistence.
The appraiser boundary belongs to condition A only; it is never given to B or C.

---

## 3. Model / serving

Model **Qwen3-4B**, local only, served via **llama.cpp (GGUF)** at **Q4_K_M** —
approved for Run 001. **No model has been downloaded or run.** The exact artifact
version and its SHA-256 digest **must be identified from the installed evaluation
artifact** (not invented); until an artifact is installed, those two fields are
**PENDING GOVERNANCE APPROVAL** and the run is blocked.

| Field | Value | Status |
|---|---|---|
| provider | `local_qwen` (local only, no cloud, no API key) | **FROZEN** |
| model | `qwen3-4b` | **FROZEN** |
| runtime / backend | llama.cpp (GGUF), injected `QwenBackend` | **FROZEN** |
| quantization | `Q4_K_M` | **FROZEN** |
| context window | `8192` | **FROZEN** |
| max output tokens | `512` | **FROZEN** |
| stop sequences | none | **FROZEN** |
| exact version | identify from the installed GGUF artifact | **PENDING** (blocking) |
| artifact / digest | SHA-256 over the exact installed artifact | **PENDING** (blocking) |
| hardware | CPU/GPU/RAM of the eval host | **PENDING** (recorded at run time) |

The runtime is **injected** (dependency injection) and provider-neutral; no runtime
is silently selected. Availability is *detected*, never fetched
(`qwen.detect_local_qwen`).

---

## 4. Prompts and schemas

Prompts and schemas are **immutable experimental artifacts** with stable IDs and
SHA-256 content hashes (`prompts.py`). The prompt texts are the ones already
implemented at the external boundaries and are **not rewritten** for this run.
Both baselines **share** one baseline prompt/schema (only their *context* differs —
a fairness requirement), so they carry the same IDs.

| Role | Prompt ID | Prompt SHA-256 | Schema ID | Schema SHA-256 |
|---|---|---|---|---|
| Evidence extraction | `extraction.observations.v1` | `a45066719aa656a3ef544d6184988fd7e42461609ef9ffbb870cf14d218697d1` | `schema.extraction.v1` | `a9cabea9ce522314e9157b39862eb8a9103b3243e507865be4716eedc161c094` |
| Evidence appraisal | `appraisal.support-contradict-propose.v1` | `790e63375fbfb49575924514b3fc277793e23ff68a6e116ffde4a3aa864e8398` | `schema.appraisal.v1` | `f36e78e0be64836de9b2df7e6aaffe0ac7087760a07c1aca6f56f2e5a1b91004` |
| Baseline (stateless) | `baseline.reasoning.v1` | `3557977b65552a1a19b3cff3a53f58b93c0efb6e802b821abe0b063cf03943bc` | `schema.baseline.v1` | `efa45b71e5043f3921048215677c04f140db7f3597b903b9b27a046582fbc11e` |
| Baseline (transcript) | `baseline.reasoning.v1` (shared) | (as above) | `schema.baseline.v1` (shared) | (as above) |

A drift guard (`prompts.verify_prompt_integrity`, preflight check
`prompt_integrity_no_drift`, and `test_prompts_registry.py`) fails if any prompt
text changes. The authoritative prompt text lives in the registry
(`prompts.PROMPTS`) and the source SYSTEM constants it references.

---

## 5. Generation parameters

The `RealRunConfig` (`qwen.qwen_real_run_config`) records these explicitly (no
implicit experimental defaults). All are **approved and frozen for Run 001**.

| Parameter | Value | Status |
|---|---|---|
| temperature | `0.0` | **FROZEN** |
| seed | `0` (policy: fixed) | **FROZEN** (honoured where the backend supports it) |
| max output tokens | `512` | **FROZEN** |
| context length | `8192` | **FROZEN** |
| stop sequences | none | **FROZEN** |
| other backend params | recorded in `ModelSpec.extra_params` | filled from the installed artifact |

Determinism note: temperature 0 + fixed seed makes the run *as reproducible as the
backend allows*; external model calls are **not** claimed to be bit-reproducible
(recorded verbatim in the manifest, §7).

---

## 6. Failure / retry policy

Implemented in `failures.py`, `validation.py`, and `manifest.call_with_recording`.
Terminal statuses (exactly six): `SUCCESS`, `MALFORMED_OUTPUT`, `MODEL_ERROR`,
`TIMEOUT`, `RETRY_EXHAUSTED`, `CONFIGURATION_ERROR`.

- **Malformed output** — any reply that is not valid JSON, has the wrong type, an
  out-of-range confidence, or a required field missing (per the strict validators)
  is **rejected** as `MALFORMED_OUTPUT`. It is **never** coerced into empty
  evidence, empty hypotheses, default values, or fabricated confidence/uncertainty.
  **Malformed output is NOT retried** (a bad schema is deterministic).
- **Model error / timeout** — a runtime failure is `MODEL_ERROR`; a timeout is
  `TIMEOUT`. These **are** retried up to the configured retry count; if still
  failing, the terminal record is `RETRY_EXHAUSTED` and the failure propagates.
- **Retry count** — **FROZEN: `retries=0` for Run 001** (`QwenClient(..., retries=0)`),
  so every failure surfaces immediately. Malformed-output handling is unchanged.
- **Raw response preservation** — the raw model text is stored on every record
  (including the offending text on a malformed failure).
- **Manifest visibility** — every call becomes a `CallRecord` (§7); per-interaction
  status is derived and rendered (`report.render_manifest_markdown`), so failures
  are visible, not hidden.
- **Hard rule** — *a failed model call can never silently become a successful
  call.* No semantic value is invented on failure; the run records the failure and
  the failure propagates.

---

## 7. Run manifest

Immutable after `finalize()` (`manifest.RunManifest`), serialized deterministically
(`sort_keys`), **stores no secrets** (credentials live with the injected client,
out of band). Captured fields:

- `run_id`, `created_at` (timestamp), `git_commit_sha`, `phase1_version`, `mode`
- `transcript_id` and the **complete transcript** (`(index, seq_label, text)` per turn)
- `model_specs` — per boundary: provider, model, prompt_id, schema_id, temperature,
  seed, model_version, max_output_tokens, context_window, `extra_params`
  (backend id, artifact availability, prompt/schema hashes, seed policy)
- `call_records` — per call: boundary, interaction_index, seq_label, model_role,
  status, attempts (retries), **raw_response**, detail, session_id, cache_id
- `per_interaction_status` — one status per interaction (incl. holds)
- prompts/schemas — referenced by immutable **ID + hash** (§4); the authoritative
  text lives in the registry
- runtime/backend metadata — via `QwenRuntimeInfo` (backend id, model id,
  model_version, artifact_id, context_window)
- session/cache identifiers — captured **where a provider exposes them**; a local
  model has none, recorded honestly as `Maybe(not_provided_by_provider)`

**Availability tri-state (`Maybe`).** Every optional field distinguishes
`available` from `not_provided_by_provider` (the provider/runtime cannot expose it)
and `not_captured` (our system did not record it). Missing values are never
invented. Reproducibility of *external model calls* is explicitly **not** claimed.

---

## 8. Case / dataset

Initial longitudinal fixture: **Case 001 — Leadership Trajectory & Organisational
Misalignment** (Registry C.6). The fixture is authoritative and **not altered** by
this manifest; the source of truth is
`fixtures/longitudinal/case_001.py` (+ `case_001_transcript.py`).

- **Interactions:** 6, in fixed order `seq-1 … seq-6`.
- **Order & hold:** processed strictly in sequence; **`seq-5` is a genuine
  no-new-evidence hold** (a real interaction with no new evidence) — preserved
  exactly, never removed.
- **Evidence sequence:** the disclosed evidence records of the fixture (referenced
  `ER-001 …`; assigned engine ids `evidence-1 …` in ingestion order). Governing
  points already encoded in the fixture and its discipline tests
  (`test_case_001_discipline.py`): `ER-006` (partner-referenced, unverified) drives
  no hypothesis change and is never cited as support; `ER-007` ("I feel better",
  resonance) appraises as empty and supports no hypothesis (Failure Conditions 1 &
  2); no fixed adverse MD-1 character judgment is permitted.
- **Candidate hypotheses:** `H1 … H4` (data-driven; the infrastructure does not
  hard-code the count).
- **What each condition receives at each step:** condition A receives the extracted
  structured evidence for that turn (into the frozen engine); conditions B and C
  receive raw turn text (B: current turn; C: accumulated). **All three process the
  same underlying ordered sequence** — enforced by the fairness guard.

The golden extractor reproduces the exact structured Case-001 trajectory from the
transcript (`test_case_001_transcript_equivalence.py`), so the REAL run substitutes
the model at the extraction/appraisal/baseline boundaries without changing the case.

---

## 9. Primary observables (raw — not scores)

Recorded per interaction, per condition (`TrajectoryRecord` + `metrics.py`). These
are **raw observables**, explicitly distinct from evaluation scores (§10, §12).
Engine-only quantities are `None` for the baselines — never fabricated.

| Observable | Source | A | B/C |
|---|---|---|---|
| Hypothesis set + continuity/revision | `hypotheses`, `retention_series` | full | re-derived only |
| Supporting evidence | `HypothesisView.supporting_evidence_ids` | yes | — |
| Contradicting evidence | `HypothesisView.contradicting_evidence_ids` | yes | — |
| Uncertainty (World-Model) | `model_uncertainty` | yes | `None` |
| Active inquiry | `inquiry` (present/absent) | yes | question text only |
| Inquiry status (§8A/§5A lifecycle) | `InquiryView.status` | yes | `""` |
| Predictions / trajectories | `predictions` | yes | — |
| Recognition-condition records | `recognition_records` | records the engine emits (currently none — computation deferred) | `None` (N/A) |
| Revision events | `revision_events`, `revision_count` | structured events | — |
| Dependency / provenance edges (§5A) | `dependency_edges` | yes | `()` |
| Unsupported-memory claims | `unsupported_memory_claims` | (engine invents none) | continuity claims without a cited evidence id |
| Evidence fidelity | extraction audit + provenance | observations only, provenance-stamped | raw text |

Mapping to Programme v1.4 §C.3 observables: **(1)** "next question the system asks"
→ inquiry present/absent + status; **(2)** "uncertainty the system flags" →
`model_uncertainty` (structurally non-comparable to baselines, which expose none);
**(3)** "hypothesis retained/revised/dropped vs re-derived" → hypothesis set +
retention + revision events. Per-step outputs follow Programme v1.4 Part 4A.

> These observables are **recorded, not judged, in this phase.** No pass/fail is
> derived from any observed value, and no criterion in this manifest was set by
> looking at any output.

---

## 12. Scoring and decision rule

Three strictly separated layers:

1. **Diagnostic measurements (code).** Raw observables (§9) and the **id-based
   hypothesis diagnostic** (`metrics.id_based_diagnostics`). The id-based measure is
   **DIAGNOSTIC ONLY** — hypothesis ids are opaque handles, not semantic identity;
   a difference here is **not** evidence that any condition reasons better and
   **must not** be converted into an evaluation score
   (`metrics.HYPOTHESIS_ID_DIAGNOSTIC_CAVEAT`). It stays a debugging aid.
2. **Semantic human evaluation.** The primary qualitative assessment of
   continuity/revision, evidence grounding, uncertainty, and inquiry quality — see
   the [Semantic Evaluation Protocol](phase1-semantic-evaluation-protocol.md)
   (§10–§11). **Approved for Run 001:** a **0–2 ordinal scale per dimension**, each
   score with written justification citing interactions, **no composite/aggregate**;
   two independent evaluators with reconciliation; neutral labels; randomised order;
   best-effort blinding.
3. **C.4 / C.5 quantitative divergence.** **Approved decision (Run 001): report raw
   longitudinal observables only** — **no** aggregate behavioural-divergence formula,
   **no** weighting, **no** numerical threshold, **no** overall Phase-1 pass/fail.
   Id-based divergence remains diagnostic only (`metrics.DIVERGENCE_RATE_STATUS`).

No Phase-1 aggregate pass/fail is produced: by decision, Phase 1 reports raw
observables plus the per-dimension human evaluation, with no composite score.

---

## 13. Pre-registration / freeze rule

**Once this manifest and the semantic protocol are approved and frozen, no
evaluation criterion, scoring rule, prompt, model parameter, condition definition,
observable definition, or interpretation rule may be changed after any results are
observed.** Any later change requires a **new protocol version** and a **separate
run**. The frozen setup is pinned by: the git SHA + `phase1_version` in the
manifest, the prompt/schema IDs + hashes (§4), the `RealRunConfig` (§3, §5), and
this document's version. No criterion in this document was set or adjusted by
looking at any existing output.

---

## Approval status summary

**AUTHORITATIVE / ALREADY AGREED**
- Objective and whole-system framing; explicitly **not** a causal/persistence-only
  claim and **not** a user-benefit claim (Programme v1.4).
- The three conditions and the state-separation/fairness rule (§2); evidence-vs-
  inference boundary and "FM proposes, frozen engine decides" (Programme v1.4
  Part 2; Reasoning Semantics v0.2).
- Provider is **local only** (`local_qwen`); no cloud, no API key, no download.
- Case 001 as the initial longitudinal fixture, unaltered (§8).
- The raw observables (§9) mapped to Programme v1.4 §C.3 / Part 4A; Inquiry status
  (Eng Spec v0.4 §8A / Sys Arch v1.1 §5A) and dependency/provenance (§5A).
- Prompts/schemas as immutable ID+hash artifacts (§4); the failure taxonomy and
  "failed calls never become successful" rule (§6); the immutable, secret-free
  manifest (§7).
- Id-based divergence is **diagnostic only** (§12); the freeze rule (§13).
- **Run-001 approvals:** runtime llama.cpp (GGUF) + quantization Q4_K_M; context
  8192; max output 512; stop none; temperature 0.0; seed 0; retries 0 (§3, §5, §6);
  C.4/C.5 = raw observables only, no aggregate/threshold/pass-fail (§12); the
  semantic 0–2 rubric, two evaluators, blinding (§10–§11); negative-result
  disposition (a null/adverse result is valid, retained unchanged, no
  result-motivated tuning). Pinned in the governance freeze record
  (`freeze_record_version 2.0-run001`).

**PENDING GOVERNANCE APPROVAL**
- Exact model artifact + version and its SHA-256 digest — **must be identified from
  the installed evaluation artifact** (§3); not invented.
- Eval hardware — recorded at run time (non-blocking).

**BLOCKING BEFORE REAL RUN**
1. Install the approved local llama.cpp runtime + Qwen3-4B Q4_K_M GGUF artifact and
   record its exact version and SHA-256 digest into the governance record and
   `RealRunConfig` → preflight `model_installed_available`,
   `model_version_identifiable`, `llama_cpp_backend_available`,
   `artifact_sha256_recorded`, and `governance_freeze_complete` flip to PASS.
2. `python -m sanuvia_phase1 preflight-real` must report **OVERALL: PASS**.
4. `python -m sanuvia_phase1 preflight-real` must report **OVERALL: PASS**.

*The real evaluation has not been executed.*
