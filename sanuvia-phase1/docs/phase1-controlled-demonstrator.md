# Phase 1 — Controlled Reasoning Demonstrator (architecture & discipline)

## 1. Purpose & scope

Demonstrate *whether* Sanuvia's persistent WorldModel yields a measurably
different reasoning **trajectory** from a stateless LLM and a transcript-context
LLM, given the **same** incrementally-disclosed evidence. Internal experiment
only — no product, chat, NLU, mediation, or Safety Gateways (Programme Part 3;
Phase 1 Brief "What this is, and isn't").

## 2. Phase 0 immutability boundary

Phase 0 (`src/sanuvia/**`, `tests/**` at the repo root, commit `9a2b501`) is
**frozen and read-only**. Phase 1 lives entirely under
`Controlled Reasoning Demonstrator/` and consumes Phase 0 only through its public
API:

- `sanuvia.application.api.ReasoningService`, `EvidenceInput`
- `sanuvia.application.reasoning.core_loop.InteractionResult` (the returned type)
- `sanuvia.adapters.reasoning.ScriptedAppraiser`
- `sanuvia.adapters.wiring.build_in_memory_dependencies`, `InMemoryReasoningStore`
- `sanuvia.adapters.support.{ManualClock, SequentialIdGenerator}`
- `sanuvia.exit_test.session_state.{SessionState, from_interactions}`,
  `sanuvia.exit_test.{trace, reasoning_graph}` renderers

Phase 1 does **not** change Core Loop, Model Revision, scoring, thresholds,
uncertainty/inquiry/prediction semantics, repository contracts, or provenance,
and adds no fields to frozen domain objects. The package is `sanuvia_phase1`
(not `sanuvia.phase1`) precisely so it cannot become a submodule of — and thus
cannot require touching — the frozen `sanuvia` package.

## 3. Condition contracts

| Condition | Class | Retained state | LLM |
|---|---|---|---|
| Sanuvia Persistent | `SanuviaPersistentCondition` | full persistent WorldModel (evidence, hypotheses, support, uncertainty, inquiry, predictions, ledger, provenance, versions) | none |
| Stateless FM | `StatelessFmCondition` | none between interactions; sees only the current evidence | `LanguageModel` |
| Transcript-context FM | `TranscriptContextFmCondition` | raw transcript text only; no structured state | `LanguageModel` |

Each condition implements `ReasoningCondition` (`start` → `step*` → `finish`),
owns its own state, and emits one `TrajectoryRecord` per interaction. The
demonstrator drives the **same immutable interaction sequence** through all three
and enforces the identical-evidence guarantee (a condition may not reorder, skip,
add, or modify disclosed evidence; seq-5 is empty for all three).

## 4. Fixture discipline (Case 001)

Authored appraisals derive **only** from the fixture's §5 evidence lists and its
evidence-role discipline — never tuned to influence the engine's inquiry.

- **Observation vs interpretation** — `CaseEvidence.text` is the RawObservation;
  participant *interpretation* is never ingested as evidence.
- **Resonance ≠ accuracy** — ER-007 ("I feel better") is appraised as empty; it
  strengthens no accuracy hypothesis (Failure Condition 2). *Verified by test.*
- **Provenance limits** — ER-006 (partner-referenced, unverified) is low
  reliability/provenance and appraised as empty; never asserted as observed
  (Failure Condition 1). *Verified by test.*
- **Retain competing hypotheses** — H1–H4 are proposed only where the fixture
  attributes their support; none is dropped. A hypothesis with no contradicting
  evidence keeps its support (H4 stays 0.3 throughout). *Verified by test.*
- **Silence ≠ disconfirmation** — seq-5 is a genuine `record_interaction(…, [])`
  hold: no new evidence, no revision, unchanged uncertainty, all hypotheses and
  supports retained. *Verified by test.*
- **No fixed MD-1 judgment** — no hypothesis/inquiry text collapses into a
  character verdict on MD-1. *Verified by test.*
- **No invented evidence** — the stored evidence is exactly the disclosed set.
  *Verified by test.*

Authoring choices (reviewable, flagged `(B)` in the fixture): placeholder
reliability floats (outside the frozen `ReasoningConfig`), proposal initial
support 0.4 (0.3 for the untested H4), H4's conservative introduction at ER-005,
and ER-003's empty appraisal (decision/emotional-salience, not accuracy).

## 5. Metric definitions (raw observables only)

Pure functions over `TrajectoryRecord` sequences. Programme v1.4 **C.5** names a
primary metric ("rate of behavioural divergence") but its thresholds/weighting are
**deferred** (C.4/C.5); we therefore expose the **raw inputs** and **do not**
compute the aggregate rate (see §12).

- `hypothesis_size_series`, `hypothesis_ids`
- `retention_series` / `retention_rate` = |Hₜ ∩ Hₜ₋₁| / |Hₜ₋₁| (`None` when Hₜ₋₁ empty)
- `inquiry_presence_series`, `observed_inquiry_pairs`
- `prediction_count_series`
- `uncertainty_series` (Sanuvia real float; FM `None`)
- `support_series` (per hypothesis; `None` where absent / FM)
- `revision_count_series`, `revision_event_count_series`, `provenance_series` (Sanuvia)
- `recognition_record_series` (Sanuvia count — normally `0`, records deferred; FM `None`)
- `unsupported_memory_series` (continuity claims with no cited evidence id — FM)
- `id_based_diagnostics` → `IdBasedDiagnosticPoint[]` (raw per-point, **DIAGNOSTIC only**; **no aggregate**)

### 5a. Per-step outputs (Programme v1.4 Part 4A)

The normalized `TrajectoryRecord` surfaces, from **real** frozen-engine fields:
active hypotheses with **`supporting_evidence_ids` and `contradicting_evidence_ids`**
(contradiction preserved, never collapsed), uncertainty, active inquiry **with its
`status`** (Eng Spec v0.4 §8A / Sys Arch v1.1 §5A lifecycle: proposed | active |
dormant | locally_resolved | reopened | superseded | closed), generated
trajectories with **`derived_from_hypothesis_ids` / `derived_from_evidence_ids`**,
**structured `revision_events`** (`RevisionEventView`: outcome, affected object,
triggering evidence, from/to model versions), and the **dependency/provenance
graph** (`dependency_edges`: `evidence —supports/contradicts→ hypothesis`,
`prediction —derived_from→ hypothesis`, …; Sys Arch v1.1 §5A "Dependency and
Provenance Relationships"; Eng Spec v0.4 §8A `DependencyEdge`; Programme v1.4
Part 4A per-step "dependencies"). FM baselines carry `None`/empty for all
engine-only fields (never fabricated).

### 5b. Recognition Conditions — records vs computation

Recognition **computation** (`detect_recognition_condition`) is interface-only and
**deferred** in Phase 0 (Programme v1.4 Part 5; Reasoning Semantics v0.2
"Recognition"); nothing writes the recognition store. The demonstrator therefore
reports `recognition_records`:

- **`()`** for the Sanuvia condition — *the engine emitted no records* (an explicit
  absence, consistent with deferred computation), **not** a fabricated "no
  recognition exists" judgment. `recognition_record_series` is `[0,…]`.
- **`None`** for FM baselines — the concept does not apply.

A test asserts no Recognition judgment is fabricated.

## 6. Observed Case 001 trajectory (deterministic)

| Interaction | seq | Sanuvia hyp size | Sanuvia uncertainty | Inquiry pair (observed) | Prediction |
|---|---|---|---|---|---|
| 1 | seq-1 | 1 | 0.300 | — | — |
| 2 | seq-2 | 2 | 0.500 | H3 / H2 | — |
| 3 | seq-3 | 2 | 0.425 | H2 / H3 | — |
| 4 | seq-4 | 4 | 0.425 | H2 / H1 | — |
| 5 | seq-5 (**hold**) | 4 | 0.425 | — | — |
| 6 | seq-6 | 4 | 0.455 | H1 / H2 | H1 (obs. traj., L=0.64) |

H1 support: `[–,–,–,0.4,0.4,0.64]` (crosses 0.6 → prediction). H4 support:
`[–,–,–,0.3,0.3,0.3]` (never disconfirmed → held). Uncertainty is **non-monotonic**.

Baselines (deterministic doubles): stateless size `[1,1,1,1,0,1]`, retention all
0/None (no accumulation); transcript size `[1,1,1,1,1,1]` (collapsed to one
narrative) with unsupported-memory claims `[0,1,1,1,1,1]`.

## 7. Inquiry behaviour (observed result)

The Case-001 *fixture* describes an ideal **H1-vs-H4** discriminating question.
The frozen engine selects inquiries by **top-two support** and pairs
`H3/H2, H2/H3, H2/H1, H1/H2` at interactions 2/3/4/6 — never H1/H4.

This is **compliant** with the authoritative requirement, not a defect:
- **Programme v1.4 C.5 (pass condition 2)** asks only that, at the final sampled
  point, inquiry targets *"a specific, World-Model-attributable uncertainty rather
  than the case as a whole."* The observed final-point inquiry **H1/H2** is exactly
  that (two named competing hypotheses with explicit support).
- A *targeted* discriminating inquiry ("which hypothesis is untested") depends on
  **Organising Objectives**, which **Reasoning Semantics v0.2 §3** states is
  *deliberately unresolved*; and the selection/assumption logic is **deferred**
  (**Programme v1.4 Part 5** "Inquiry reopening / Non-convergence measure — interface
  only"; **Part 8 "Delay"**).
- Not forcing H1/H4 satisfies **Programme v1.4 Part 9A**: *"No unresolved transition
  function is silently hard-coded to achieve the result."*

Recorded as an observed result (Programme v1.4 **C.1** authorises non-divergence /
inquiry outcomes as *negative results*, not scoring failures). The engine correctly
**surfaces an inquiry rather than narratively resolving** (≥2 hypotheses stay live)
and **retains H1–H4** through the hold and to the end.

## 8. FM baseline boundary

Official baselines are foundation-model-backed via the `LanguageModel` port. The
FM response contract (§9-style constrained JSON) is parsed by
`capture.parse_baseline_turn` — a strict structured reader, **not** an NLU parser
for arbitrary prose. `ExternalLanguageModel` wraps a caller-injected client (no
vendor bundled; `language_model_from_env()` refuses to auto-select). Prompt design
affects baseline fairness and is a governance item.

## 9. Deterministic vs real evaluation

- **Deterministic (CI, default):** `ScriptedLanguageModel` returns pre-authored
  archetype JSON per interaction → the whole demonstrator is byte-identically
  reproducible (`report.to_json` stable across runs). These doubles are **stylized
  archetypes**, not empirical LLM output; the CI tests assert *plumbing/metrics
  correctness*, never "Sanuvia wins."
- **Real (opt-in):** `ExternalLanguageModel` with an approved provider/model.
  Nondeterministic; produces recorded artifacts; **no thresholds asserted**.

## 9a. Real transcript pipeline (raw text → extraction → Phase 0)

`transcript.py` / `extraction.py` / `evidence_extractors/` / `pipeline.py` add the
real front end (Programme v1.4 Part 3 Phase 1 — "feed the Phase 0 core real
relationship-conversation transcripts").

```
raw transcript text ─► EvidenceExtractor ─► structured evidence ─► frozen Phase 0 ─► trajectory
        └─► FM baselines read raw transcript text (no structured state)
```

- **Extraction contract** (`EvidenceExtractor.extract(interaction, transcript_id) → ExtractedEvidence[]`):
  raw text → **observations only**, each with `EvidenceProvenance` (source interaction,
  transcript id, extractor id, text span, status). The extractor **never** forms
  hypotheses or touches Phase-0 state (Reasoning Semantics v0.2 "Evidence" vs
  "Hypothesis"; Programme v1.4 Part 2 evidence≠inference). Provenance flows into the
  Phase-0 evidence record via the public `EvidenceInput.acquisition_metadata` — **no
  Phase-0 change**.
- **Appraisal stays Phase 0.** Turning evidence into hypotheses is the frozen
  `EvidenceAppraiser` port — `ScriptedAppraiser` in golden mode; the provider-neutral
  **`ExternalEvidenceAppraiser(client=…)`** seam (`evidence_appraisers/`) in real
  mode. The appraiser only **proposes** candidate hypotheses + support/contradiction;
  the frozen engine still owns model revision and persistence (a test asserts the
  `hypothesize` revision and model version come from the engine, not the appraiser).
  The extractor and the appraiser are distinct responsibilities; the provider/model
  and appraisal prompt/schema remain governance (see §10).
- **Two modes**, always tagged in the report: **GOLDEN** (`ScriptedEvidenceExtractor`,
  byte-identical) and **REAL** (`ExternalEvidenceExtractor(client=…)`, injected,
  non-deterministic; no provider bundled, `evidence_extractor_from_env()` refuses to
  auto-select).
- **Fairness:** Sanuvia reasons over the *extracted structured evidence*; the FM
  baselines read the *raw transcript text* (stateless: current turn; transcript-context:
  all prior turns). A guard enforces the same ordered interaction sequence across all
  three (this is the correct "structured reasoning vs raw context" comparison —
  Programme v1.4 Part 4A).
- **Golden equivalence:** Case 001 as a transcript + the golden extractor yields the
  **identical** Sanuvia trajectory as the structured fixture (asserted by test).

## 10. Unresolved governance decisions (not resolvable in code)

1. **FM provider/model** and serving arrangement (Programme v1.4 Part 6A) — not selected.
   This now covers **two** injected boundaries: the **FM baselines** *and* the **real
   evidence-extraction / appraisal adapters**.
2. **Evidence-extraction prompt/schema** and **FM prompt / structured-output contract**
   sign-off — affects fairness and extraction quality.
3. **Real-mode appraiser** — the **seam is implemented** (`ExternalEvidenceAppraiser`,
   injected client, port-conformant). Its **provider/model + appraisal prompt/schema**
   remain unresolved — the **same class of blocker** as the FM baselines.
4. **Temperature/seed/determinism** for real runs — *not specified by the supplied documents.*
5. **C.4/C.5 numerical thresholds** and confirmation of the C.5 draft pass conditions — deferred to the programme governance process.
6. **Formal acceptance of the negative-result disposition** (Programme v1.4 C.1) for the inquiry outcome.

Until these are set, only the deterministic doubles run; the demonstrator is **not
"fully evaluation-ready."**

### Authoritative document versions (gate resolved)
**System Architecture v1.1** and **Engineering Specification v0.4** are now
available and reconciled (alongside Programme v1.4 and Reasoning Semantics v0.2).
The earlier version gate is **resolved**. Reconciliation outcomes:

- **PredictionLikelihood** (6th uncertainty type, Eng Spec v0.4 §2.0) — confirmed;
  frozen Phase 0 implements it; Phase 1 surfaces it (`PredictionView.likelihood`).
- **Inquiry status lifecycle** (§8A / §5A) — frozen Phase 0 implements the full
  enum; Phase 1 now surfaces it (`InquiryView.status`).
- **Dependency/provenance graph** (§5A / §8A `DependencyEdge`) — frozen Phase 0
  writes edges; Phase 1 now surfaces them (`dependency_edges`).

### Frozen-Phase-0-vs-v0.4 discrepancies (report only — Phase 0 is frozen)
Two shape deviations between the **frozen** Phase 0 and Eng Spec v0.4 §8A were
found. Phase 0 is signed-off/frozen, so these are **reported, not changed**, and
neither blocks the demonstrator:

1. **Prediction trajectories.** Frozen Phase 0 models `Prediction.trajectory:
   FutureTrajectory` (one trajectory per Prediction; multiple trajectories = multiple
   Prediction records). Eng Spec v0.4 §8A / Sys Arch v1.1 §5A model
   `Prediction.trajectories: List<FutureTrajectory>` with a `divergence_point`
   between co-trajectories. Consequence: Phase 1 cannot surface an intra-prediction
   `divergence_point`. **Owner decision** (would require unfreezing Phase 0).
2. **DependencyEdge / RecognitionCondition status fields.** Frozen `DependencyEdge`
   has no `invalidated_at`; frozen `RecognitionEvent` has no `pending|met|expired`
   status (§8A `RecognitionCondition` defines both). Immaterial to Phase 1 today
   (edges are append-only here; no recognition records are emitted), but noted.

## 11. Coverage fixtures (Programme v1.4 Part 4A test structure)

Focused ≥5-interaction probes that exercise the **real** frozen API through the
demonstrator (Case 001 unchanged):

- `prediction_invalidation.py` — a prediction forms (support crosses the threshold)
  then is **invalidated** when a contradiction drops support back below it
  (`prediction_count [0,1,0,0,0]`; contradiction revision on the affected hypothesis).
- `failed_acquisition.py` — a `FAILED_ACQUISITION`-class record whose appraisal
  proposes **two competing candidate explanations** (not a single default) and is
  **recorded, not discarded** — faithful to the six-class evidence protocol
  (Programme v1.4 Part 2; Eng Spec §3/§4.4, held at v0.2). The frozen engine does not
  special-case the class, so the protocol is represented via multiple proposals.

## 12. Divergence rate — status

Programme v1.4 **C.5** names *"rate of behavioural divergence"* the primary metric,
but the supplied documents define **no formula, weighting, or similar/diverged
threshold** (C.4/C.5 defer them). `metrics.id_based_diagnostics()` exposes raw
per-point comparisons across the three C.3 dimensions (`IdBasedDiagnosticPoint`); the
aggregate rate is **not computed** and `metrics.DIVERGENCE_RATE_STATUS` records it
as pending governance. No monotonicity rule, weight, or pass/fail is invented.

**The hypothesis-set comparison is `id`-based and is a DEBUGGING DIAGNOSTIC only.**
A hypothesis id is an opaque handle, not a semantic identity — two conditions can
express the same reading under different ids, or drift under a stable id. So an id
difference is **not** a semantic continuity/revision evaluation and is **not**
evidence that Sanuvia reasons better or worse than a baseline
(`metrics.HYPOTHESIS_ID_DIAGNOSTIC_CAVEAT`; reports print the caveat inline). The
semantic evaluation protocol (continuity/revision, uncertainty, inquiry quality)
is defined **separately** by the programme team and is not implemented here.

## 13. Hardening — GOLDEN/REAL guard, validation, manifest, stateless context

Before the real comparison the following were hardened (additive, Phase-0 untouched):

- **Configuration consistency** (`runconfig.py`): `validate_run_configuration()`
  runs *before execution*. GOLDEN accepts only scripted doubles; REAL accepts only
  non-scripted components plus a complete `RealRunConfig` (explicit provider,
  model, version, prompts, schemas, parameters). GOLDEN never pretends to be REAL;
  REAL never silently falls back to scripted. No provider is auto-selected.
- **Strict output validation** (`validation.py`): every external boundary
  (extraction, appraisal, stateless, transcript) is schema-validated. Malformed
  output is **rejected** (`MalformedOutputError`), never coerced into empty
  evidence/hypotheses, default values, or fabricated confidence/uncertainty. An
  *absent* optional key is a legitimately empty answer (documented), distinct from
  malformed output. Statuses are `SUCCESS`, `MALFORMED_OUTPUT`, `MODEL_ERROR`,
  `TIMEOUT`, `RETRY_EXHAUSTED`, `CONFIGURATION_ERROR` (`failures.py`).
- **Immutable run manifest** (`manifest.py`): captures run id, timestamp, git SHA,
  Phase-1 version, mode, the full transcript, model specs, raw responses, retries,
  failures, and per-interaction status; frozen after `finalize()`; deterministic
  JSON; stores no secrets. Provider-absent fields (model version, seed, session/
  cache id) use `Maybe`, distinguishing *not provided by provider* from *not
  captured*. External model calls are **not** claimed reproducible.
- **Stateless context guarantee**: the stateless baseline sends exactly the current
  interaction's evidence each turn — no prior messages/output/state — proven in
  `tests/phase1/test_stateless_context_guarantee.py`.

## 13a. REAL Qwen boundary + preflight (executable, not executed)

The first REAL evaluation uses a **small local Qwen** model. Nothing is downloaded
or auto-selected.

- **Candidate model** (`qwen.QWEN3_4B`): **Qwen3-4B** (project direction), ~4B
  params, ~2.5 GB Q4 GGUF, ~6 GB working RAM; smaller fallbacks `qwen3-1.7b` /
  `qwen3-0.6b`. Recommended local runtimes: Ollama (`qwen3:4b`), llama.cpp GGUF,
  transformers (`Qwen/Qwen3-4B`).
- **Client boundary** (`qwen.QwenClient`): provider-neutral, injected, local-only —
  no vendor SDK import, no API key, no network. It composes prompts, records every
  call in the manifest (`begin_interaction` attributes each call to an
  interaction/seq), classifies errors/timeouts, records retries, and adapts to the
  existing `ExternalEvidenceExtractor` / `ExternalEvidenceAppraiser` /
  `ExternalLanguageModel` seams. Qwen logic never enters the frozen Phase 0 engine.
- **RealRunConfig** (`qwen.qwen_real_run_config`): `provider=local_qwen`, model
  `qwen3-4b`, explicit prompt/schema IDs, temperature `0.0`, seed `0`,
  max-output/context set; exact model version + artifact digest are `Maybe`
  (recorded unavailable until a runtime supplies them).
- **Prompts/schemas** (`prompts.py`): existing prompt texts registered under stable
  IDs with SHA-256 drift detection; both baselines **share** `baseline.reasoning.v1`
  (only their context differs — fairness).
- **Preflight**: `PYTHONPATH=src python -m sanuvia_phase1 preflight-real` reports PASS/BLOCKED for
  config completeness, prompt/schema presence + integrity, no-scripted-double,
  local-only, model availability + version, Phase-0 import isolation, and Phase-0
  git-untouched — **without running the model or the comparison**.

## 13. Observed limitations (summary)

1. Frozen inquiry never selects the fixture's ideal H1/H4 pair — compliant per C.5
   (§7); targeted selection deferred.
2. FM doubles are stylized archetypes (no empirical LLM claim); real evaluation is
   governance-blocked.
3. Coverage fixtures are focused probes; the full longitudinal case *set* grows over time.
4. Aggregate divergence rate and all thresholds are deferred to governance.
5. System Architecture v1.1 / Eng Spec v0.4 not supplied — not certifiable here.
