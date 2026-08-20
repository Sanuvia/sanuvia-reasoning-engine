# Controlled Reasoning Demonstrator (Sanuvia Phase 1)

An **internal reasoning experiment** that drives one longitudinal evidence
sequence through three conditions and records a normalized reasoning *trajectory*
for each, so they can be compared:

- **A. Sanuvia Persistent** — the frozen Phase 0 Persistent Reasoning Core.
- **B. Stateless FM baseline** — a foundation model given only the current evidence.
- **C. Transcript-context FM baseline** — a foundation model given all prior transcript text.

It is **not** a product, chat app, NLU system, mediation layer, or Safety Gateway.

## Purpose

Demonstrate *whether* Sanuvia's persistent WorldModel produces a **measurably
different reasoning trajectory** from the two baselines, given the **same**
sequential evidence disclosed incrementally. This realises **Programme v1.4
Part 4 Section C (Longitudinal Behavioural Validation)**: behaviour is sampled at
multiple points across a case, recording the three C.3 observables (inquiry,
uncertainty, hypothesis retained/revised/dropped-vs-re-derived) for all three
conditions.

Programme v1.4 **C.5** names *"rate of behavioural divergence"* as the **primary
metric**, but its numerical thresholds, weighting, and pass/fail criteria are
**explicitly deferred** (Programme v1.4 C.4/C.5 — "set with Felix and both
developers"). This demonstrator therefore exposes the **raw per-point
observables** and marks the **aggregate divergence rate as pending governance**;
it invents no formula or threshold.

## Real transcript pipeline (two modes)

The full Phase 1 flow turns **raw conversation text** into structured evidence and
feeds the **frozen Phase 0 engine** — the LLM is an *evidence-extraction*
component, **not** the reasoning engine:

```
raw transcript text ──► EvidenceExtractor ──► structured evidence ──► FROZEN PHASE 0 ──► persistent World Model ──► trajectory
        │                                                                                                              ▲
        └──► FM baselines read raw transcript text (stateless: current turn; transcript-context: all prior turns) ─────┘
```

- **What the LLM does:** extract *observations* from text (`raw text → observations`).
- **What the LLM does NOT do:** revise the model, set uncertainty, produce
  predictions/inquiry, or touch any Phase-0 state. Turning evidence into hypotheses
  is the frozen Phase-0 `EvidenceAppraiser` port — `ScriptedAppraiser` (golden) or
  `ExternalEvidenceAppraiser(client=…)` (real seam): the appraiser only **proposes**;
  the **frozen engine decides** revision/persistence. **LLM ≠ Sanuvia reasoning engine.**
- **Evidence vs inference:** the extractor emits *observations* only
  ("Person 1 said …"), never interpretations ("Person 1 fears rejection"); the
  reasoning engine later forms hypotheses. Every extracted item retains provenance
  (source interaction, transcript, extractor id, text span, status).

**Two explicit modes** (a run is always tagged, never mixed silently):

| Mode | Extractor | Determinism | Purpose |
|---|---|---|---|
| **GOLDEN** | `ScriptedEvidenceExtractor` | byte-identical | regression / replay / equivalence |
| **REAL** | `ExternalEvidenceExtractor(client=…)` | not guaranteed | actual transcript processing |

Case 001 exists both as the structured fixture **and** as a transcript
(`case_001_transcript.py`); the golden extractor reproduces the **identical**
Sanuvia trajectory from the transcript (asserted by test).

Run it:
```python
from fixtures.longitudinal.case_001_transcript import (
    CASE_001_TRANSCRIPT, case_001_scripted_extractor,
    CASE_001_APPRAISAL_SCRIPT, CASE_001_HYPOTHESIS_CATALOGUE)
from fixtures.longitudinal.case_001_baseline_scripts import deterministic_language_models
from sanuvia_phase1 import pipeline, report
s, t = deterministic_language_models()
tdr = pipeline.run_transcript_demonstration(
    CASE_001_TRANSCRIPT, case_001_scripted_extractor(),
    CASE_001_APPRAISAL_SCRIPT, CASE_001_HYPOTHESIS_CATALOGUE, s, t,
    case_id="case-001-transcript", mode=pipeline.GOLDEN)
print(report.render_transcript_markdown(tdr))
```

## Phase 0 vs Phase 1 boundary

Phase 0 is **frozen and read-only**. This directory is the entire Phase 1
boundary. Nothing here modifies Phase 0; the Sanuvia condition consumes only the
public Phase 0 API (`ReasoningService`, `WorldModelView`, `ScriptedAppraiser`,
`build_in_memory_dependencies`, and the `exit_test` trace/graph renderers).

The Phase 1 package is importable as **`sanuvia_phase1`** (a distinct top-level
package). It is *not* `sanuvia.phase1`: the frozen `sanuvia` is a regular package,
so adding a `sanuvia.phase1` submodule would require changing Phase 0 (forbidden).

## Directory structure

```
Controlled Reasoning Demonstrator/
├── fixtures/longitudinal/
│   ├── case_001.py                         # Case 001 (Registry C.6) evidence + appraisal script
│   ├── case_001_transcript.py              # Case 001 as raw TRANSCRIPT + golden extractor
│   ├── case_001_baseline_scripts.py        # deterministic FM test-double archetype responses
│   ├── prediction_invalidation.py          # coverage: prediction invalidation (Part 4A)
│   ├── failed_acquisition.py               # coverage: failed evidence acquisition (Part 4A)
│   └── toy_case.py                         # variable-N case (proves data-driven hypotheses)
├── src/sanuvia_phase1/
│   ├── transcript.py      # Transcript / TranscriptInteraction (raw text input)
│   ├── extraction.py      # EvidenceExtractor port + ExtractedEvidence + provenance
│   ├── evidence_extractors/# scripted (test double) + external (real, injected client)
│   ├── evidence_appraisers/ # external appraiser seam (real; injected client)
│   ├── pipeline.py         # transcript → extraction → Phase 0 runner (golden/real modes)
│   ├── case.py            # Case / CaseEvidence / CaseInteraction DTOs
│   ├── ports.py           # LanguageModel port (+ LmRequest/LmResponse)
│   ├── trajectory.py      # TrajectoryRecord + view DTOs + BaselineTurn
│   ├── capture.py         # normalization: InteractionResult / BaselineTurn -> TrajectoryRecord
│   ├── metrics.py         # pure raw-metric functions
│   ├── demonstrator.py    # structured-case orchestration + identical-evidence guard
│   ├── report.py          # canonical JSON + markdown (structured + transcript) + trace reuse
│   ├── conditions/        # base + sanuvia + fm_stateless + fm_transcript
│   └── language_models/   # scripted (test double) + external (real seam)
├── tests/phase1/          # the Phase 1 test suite
├── docs/phase1-controlled-demonstrator.md
├── conftest.py            # local pytest path bootstrap (adds src + this dir)
└── pyproject.toml         # local pytest/mypy config (does not touch Phase 0)
```

## How to run

All commands run **from this directory** (`Controlled Reasoning Demonstrator/`),
using the repo's virtualenv, with the frozen `sanuvia` already installed
(editable) in that environment.

**Deterministic tests (default CI path — no network/vendor):**
```bash
cd "Controlled Reasoning Demonstrator"
python -m pytest            # 65 tests
python -m mypy src fixtures tests   # strict, clean
```

**Run Case 001 and print the trajectory report:**
```bash
python - <<'PY'
from fixtures.longitudinal.case_001 import CASE_001
from fixtures.longitudinal.case_001_baseline_scripts import deterministic_language_models
from sanuvia_phase1 import demonstrator, report
stateless, transcript = deterministic_language_models()
conds = demonstrator.build_default_conditions(CASE_001, stateless, transcript)
rep = demonstrator.run(CASE_001, conds)
print(report.render_markdown(rep))
PY
```

**Deterministic replay** (byte-identical): `report.to_json(rep)` is stable across
runs of the deterministic path (a test asserts this).

## The three conditions

| Condition | Backend | Retained state |
|---|---|---|
| `sanuvia_persistent` | frozen Phase 0 engine | full persistent WorldModel: evidence, hypotheses, support, uncertainty, inquiry, predictions, revision ledger, provenance, model versions |
| `fm_stateless` | `LanguageModel` | **none** between interactions (only the current evidence is shown) |
| `fm_transcript` | `LanguageModel` | **raw transcript text only** — no structured hypotheses/support/uncertainty/ledger/WorldModel |

Engine-only quantities (support, uncertainty, revision count, provenance, model
version) are **`None`** for the FM conditions — never faked.

## Enabling real foundation-model evaluation (opt-in)

The two FM baselines run behind `LanguageModel`. CI uses the deterministic
`ScriptedLanguageModel`. For real evaluation, construct an `ExternalLanguageModel`
with your own client and pass it to the FM conditions:

```python
from sanuvia_phase1.language_models import ExternalLanguageModel
model = ExternalLanguageModel(client=my_client)   # my_client(LmRequest) -> raw JSON str
```

No provider/model is bundled or auto-selected (`language_model_from_env()` raises
on purpose). **Provider/model/prompt governance is unresolved** and must be agreed
(this is Programme Part 6A / prompt-fairness). Real runs are **not** deterministic.

## Per-step outputs & Recognition Conditions

Each `TrajectoryRecord` surfaces the Programme v1.4 Part 4A per-step outputs from
**real** frozen-engine fields (Sanuvia condition; FM baselines carry `None`/empty):
active hypotheses **with supporting *and* contradicting evidence**, uncertainty,
active inquiry, generated trajectories **with `derived_from_hypothesis_ids` /
`derived_from_evidence_ids`**, and **structured `revision_events`** (not just a
count).

**Recognition Conditions — records vs computation.** Recognition *computation*
(`detect_recognition_condition`) is interface-only and **deferred** in Phase 0, so
the engine writes **no** Recognition records. The demonstrator surfaces
`recognition_records` = **`()`** for Sanuvia (an explicit "engine emitted none",
*not* a fabricated "no recognition exists" judgment) and **`None`** for FM
baselines (concept not applicable). No Recognition judgment is ever fabricated.

## Divergence rate status

Programme v1.4 **C.5** names *"rate of behavioural divergence"* as the primary
metric. The supplied authoritative documents define **no computable formula,
weighting, or similar/diverged threshold** (deferred, C.4/C.5). `metrics.py`
therefore exposes **raw per-point `divergence_observables`** across the three C.3
dimensions and publishes `metrics.DIVERGENCE_RATE_STATUS = "PENDING GOVERNANCE…"`.
No aggregate rate, weighting, or threshold is invented.

## Deliberately NOT implemented

- No product, chat UX, NLU parser, mediation, or Safety Gateways.
- No change to Phase 0 (engine, scoring, thresholds, semantics, tests).
- **No aggregate divergence rate / threshold / pass-fail** — the C.5 primary
  metric's numerical definition is deferred to governance (C.4/C.5); only raw
  observables are exposed.
- No `RelationshipModel`, `evidence_role` field, targeted-EIG inquiry, Recognition
  **computation**, inquiry-reopening/non-convergence logic, or revision escalation
  (`evidence_role` exists only as fixture metadata; those transition functions are
  deferred — Programme v1.4 Part 5/Part 8; Reasoning Semantics v0.2 §3).
- No real FM provider chosen.

## Governance blockers (pending — not resolvable in code)

1. FM provider/model · 2. FM serving arrangement · 3. FM prompt/structured-output
contract · 4. temperature/seed/determinism for real FM · 5. C.4/C.5 numerical
thresholds · 6. confirmation of the C.5 draft pass conditions · 7. formal
acceptance of the negative-result disposition (Programme v1.4 C.1).
Until these are set, **only the deterministic doubles run** and the demonstrator
is **not "fully evaluation-ready."**

## Authoritative documents (version gate resolved)

All four governing documents are reconciled: **Programme v1.4**, **System
Architecture v1.1**, **Engineering Specification v0.4**, **Reasoning Semantics
v0.2**. Per-step outputs now include the **Inquiry status lifecycle** (§8A/§5A)
and the **dependency/provenance graph** (§5A/§8A `DependencyEdge`), both produced
by the frozen Phase 0 engine. Two frozen-Phase-0-vs-v0.4 shape deviations
(single-trajectory `Prediction`; missing `DependencyEdge.invalidated_at` /
`RecognitionCondition` status) are **reported, not changed** — Phase 0 is frozen;
see `docs/phase1-controlled-demonstrator.md`.

## Known limitations

- **Inquiry pair (observed).** With Case 001, the frozen support-driven top-two
  inquiry selects `H3/H2, H2/H3, H2/H1, H1/H2` at interactions 2/3/4/6 — it never
  selects the *fixture's ideal* **H1-vs-H4** pair. This is **compliant** with the
  authoritative requirement (Programme v1.4 C.5 asks only for a "specific,
  World-Model-attributable uncertainty" at the final point — H1/H2 qualifies);
  *targeted* discriminating inquiry depends on the deliberately-unresolved
  Organising Objectives (**Reasoning Semantics v0.2 §3**) and deferred selection
  logic (**Programme v1.4 Part 5/Part 8**). Recorded as an observed result, not
  engineered away.
- **FM doubles are stylized** archetypes; no empirical claim about real LLMs.
- **Coverage fixtures are focused probes** (5 interactions each) exercising the
  real API for prediction-invalidation and failed-acquisition; the full
  longitudinal case *set* still grows over time.

See `docs/phase1-controlled-demonstrator.md` for full detail.
