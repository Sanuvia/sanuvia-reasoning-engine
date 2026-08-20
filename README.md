# Sanuvia — Persistent Reasoning Core (Phase 0)

> The foundation model does not own the persistent reasoning state. Sanuvia does.

This repository implements **Phase 0 (the Persistent Reasoning Core)** of the
Sanuvia Implementation Programme. Its single purpose is to prove the engine
**reasons over time**: it accumulates evidence, revises a versioned model,
retains competing hypotheses, and updates predictions as new evidence arrives.

It is **not** a chat app, a mediation engine, or a product. There is no UI, no
mediation output, and no Safety Gateways in this phase — those begin at Phase 2.
If it starts to look like a chat demo, that is out of scope.

## Source of truth

The specification governs; this code implements it. When code and spec disagree,
the spec wins.

- **Sanuvia Blueprint (Founding Edition)** — *why* (product philosophy, reasoning objects).
- **Sanuvia Implementation Programme v1.3** — *what to build first, and the finish line*.
- **Phase 1 Prototype Brief** — the Phase 0/1 build list and Evaluation Protocol.
- **System Ownership & Runtime Architecture artefacts** — the frozen `FR-*` requirements.

Every domain class and port is annotated with the `FR-*` requirement it realises.

## Architecture — clean / hexagonal, deployment-agnostic

The core must run in the cloud today and self-hosted tomorrow **without changes
to the domain or application layers**. Only adapters and wiring change.

```
src/sanuvia/
  domain/        Pure reasoning objects + invariants. Standard library only.
                 No framework, no cloud SDK, no foundation model, no I/O.
                 The single source of truth for the data model.
  application/
    ports/       Interfaces the core depends on: repositories + support
                 (Clock, IdGenerator, ModelProvider). No infrastructure here.
  adapters/      [later increments] Concrete ports: persistence, API, FM access.
                 Cloud-specific code, if any, lives here only.
```

Dependency rule: `adapters → application → domain`. The domain imports nothing
from the application or adapters; the application imports no adapter. This is
enforced automatically by `tests/test_architecture.py`, which fails the build if
the core acquires a framework/cloud/FM import.

## What exists in this increment

The **complete domain model** and the **repository + support ports** — built
before any reasoning logic, per the kickoff sequencing.

| Capability | Objects | FR |
|---|---|---|
| Evidence | `EvidenceRecord`, `InferenceRecord` (never conflated), `EvidenceClass` ×6 incl. Failed Acquisition, `Provenance` | FR-EM-001..005 |
| Persistent Understanding | `WorldModel` (immutable versions), `CurrentModelSnapshot`, `ProvenanceRecord`, `SystemModellingContext` | FR-PU-001..005 |
| Reasoning | `Hypothesis` (+`HypothesisSupport`), `Prediction`/`FutureTrajectory` (+`PredictionLikelihood`) | FR-RS-001..005 |
| Inquiry | `Inquiry`, `InquiryStatus` lifecycle | FR-IQ-001..006 |
| Model Revision | `AnomalyResolution`/`AnomalyDisposition`, `RevisionEvent` (proposed→committed), `RevisionOutcome`, `ModelRevisionResult` (multiple events), `RevisionLedgerEntry` | FR-MR-001..005 |
| Recognition | `RecognitionEvent`, `RecognitionKind` (data only) | FR-RF-001/002/004 |
| Cross-cutting | six typed uncertainties, `DependencyEdge`, `CognitiveState`, `AcquisitionStrategy` | — |

### Design guarantees worth calling out

- **Evidence vs. Inference cannot be conflated.** They are unrelated types; an
  inference can never be re-ingested as evidence (FR-EM-005). The evidence and
  inference stores are separate ports — no method anywhere accepts an inference
  as evidence.
- **Uncertainty is six distinct types, never one float** (Programme Part 2).
  `ModelUncertainty` can *increase*, not merely decrease.
- **Immutability + append-only.** WorldModel versions, evidence, and ledger
  entries are frozen; correction happens through revision, never mutation.
- **No relationship-failure predictions, ever.** `TrajectoryKind` and
  `RecognitionKind` simply cannot express failure (FR-RF-002).
- **Reasoning terminates at Inquiry, never a Recommendation.** No Recommendation
  object exists.

### Deliberately deferred (represented as data / interface only — never faked)

Per the frozen spec, these transition functions are unresolved. Phase 0 models
the affected objects but does not implement the logic, and must not hard-code it
to force a result:

- `proposed → committed` revision governance
- Model Revision escalation / second-order revision / assumption-selection
- `detect_recognition_condition` (Recognition Condition computation)
- Inquiry reopening threshold / non-convergence measure
- Structured multi-dimensional `CognitiveState` (explicit non-goal; single enum used)

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest                    # domain invariants + architecture guards + exit test
mypy                      # strict type checking of the core
python -m sanuvia.exit_test               # the Phase 0 proof: PASS/FAIL per condition
python -m sanuvia.exit_test.trace         # human-readable longitudinal reasoning trace
python -m sanuvia.exit_test.trace --write reasoning_trace.md   # write it to a file
python -m sanuvia.exit_test.reasoning_graph --write reasoning_graph.md   # lineage graph
python -m sanuvia.exit_test.reasoning_graph --dot reasoning_graph.dot    # Graphviz DOT
```

### The Phase 0 exit test

`python -m sanuvia.exit_test` runs a fixed, synthetic six-interaction evidence
sequence through the reasoning engine on in-memory adapters (no infrastructure,
no foundation model) and verifies every pass condition: WorldModel versions are
appended never mutated, competing hypotheses are retained, predictions are
revised as evidence changes, ModelUncertainty both rises and falls, a Failed
Acquisition yields competing candidates, no inference is stored as evidence,
every revision is traceable to evidence via the ledger, and the run is
reproducible. Exit code 0 = the proof holds.

### The reasoning trace

`python -m sanuvia.exit_test.trace` renders a deterministic, human-readable
Markdown narrative of the same scenario — per interaction: incoming evidence, the
WorldModel version before revision, competing hypotheses and their support
changes, any AnomalyResolution, the RevisionEvents created, the new immutable
version, active predictions, any Inquiry, and ModelUncertainty before/after — then
end-of-run summaries (RevisionLedger, hypothesis lineage, prediction history,
uncertainty timeline). Every value is read from the engine's own outputs and
persisted state, so it is byte-for-byte reproducible. See `reasoning_trace.md`.

### The reasoning lineage graph

`python -m sanuvia.exit_test.reasoning_graph` is the **visual companion** to the
trace. It builds a neutral graph model **automatically from the RevisionLedger and
the immutable reasoning objects** — the WorldModel version spine (labelled with
committed outcomes), evidence→hypothesis edges (solid = strengthen/hypothesise,
dashed = contradict), hypothesis→prediction edges, version→inquiry edges, and
anomaly resolutions (linked to a version when they drove a revision, to evidence
only when they escalated) — and renders it to **Mermaid** (embedded in
`reasoning_graph.md`, renders in any Mermaid-aware viewer) and **Graphviz DOT**.
Nothing is hand-drawn or scenario-special-cased; both renderings are
deterministic and reproducible.

## Reasoning engine (this increment)

`application/reasoning/` holds the **genuine** reasoning — the invention — driven
entirely through ports:

- **`ModelRevisionEngine`** (the centerpiece): appraised evidence → support &
  uncertainty revision → contradiction handling via `AnomalyResolution` →
  traceable `RevisionEvent`s → committed into a new immutable `WorldModel`
  version → regenerated predictions → an `Inquiry` when competition warrants it.
- **`CoreLoop`**: the full cycle in spec order (`get_current_model → … →
  revise_model`), returning an `InteractionResult` with the Evaluation Protocol's
  required outputs.

The seams that keep this honest are ports with Phase-0 placeholder adapters
(`adapters/reasoning/`): the `EvidenceAppraiser` (language-understanding boundary
— an FM later), the `RevisionCommitPolicy` (spec-unresolved governance), and the
`CognitiveStateProvider`. In-memory persistence adapters (`adapters/persistence/`)
implement every repository port for tests and the exit-test harness.

A longitudinal scenario test (`tests/reasoning/`) demonstrates the model revising
across interactions, hypotheses competing, uncertainty rising on destabilisation
and falling on consolidation, predictions being generated and invalidated, a
failed acquisition producing competing candidates, and an escalation holding the
model.

## API contract (this increment)

`application/api/` defines the framework-free contract both engineering tracks
code against:

- **`ReasoningService`** (write): callers hand in `EvidenceInput` DTOs; the
  service assigns ids/timestamps via ports, builds immutable `EvidenceRecord`s,
  and runs one Core Loop interaction. The only intake DTO is evidence — there is
  no path to hand in an inference, so FR-EM-005 holds at the boundary too.
- **`WorldModelView`** (read): a distinct type with **no mutating method on its
  surface** — the structural enforcement of "the Content Layer never mutates
  reasoning". It returns immutable snapshots (`WorldModelViewSnapshot`) of current
  understanding. A test asserts the view exposes no mutator.

The contract is framework-free by design. An HTTP transport (e.g. FastAPI) is a
thin adapter over `ReasoningService` / `WorldModelView`, added later without
touching the core — exactly like the SQLite persistence adapter.

See `docs/phase0-design-notes.md` for notes on the Phase-0 scaffolds
(`ScriptedAppraiser`, `ReasoningConfig` placeholders, `PlaceholderCommitAllPolicy`)
and the determinism guarantee.

## Persistence adapters

Two interchangeable backends implement the same repository ports:

- **In-memory** (`adapters/persistence/in_memory.py`) — for tests and the exit
  test.
- **SQLite** (`adapters/persistence/sqlite_store.py`) — durable, standard-library
  only, using a JSON codec to persist whole immutable reasoning objects. Wire it
  with `build_sqlite_dependencies(path=...)`.

The SQLite adapter is pure infrastructure: a test runs the identical canonical
scenario through both backends and asserts **byte-identical** reasoning, proving
the backend changes only *where* state lives, never *how* reasoning behaves.
State survives across connections.

### Isolation: space / subject / actor

All reasoning state is owned by a `(space_id, subject_id)` boundary — three
distinct identifiers that are never collapsed: **`space_id`** (where reasoning
belongs — the isolation boundary), **`subject_id`** (who/what it concerns), and
**`actor_id`** (who contributed a piece of evidence). Repositories partition by
`(space, subject)`, so a query for one scope can never return another's
hypotheses, predictions, or world model; evidence whose ownership doesn't match
the interaction scope is rejected. The SQLite adapter migrates a pre-space
database in place (`sqlite_migration.py`). Negative regression tests
(`tests/test_space_isolation.py`) prove cross-boundary access fails. Single-space
callers are unaffected — the default space keeps existing behaviour byte-identical.

Reset/rerun semantics (deterministic test harness vs. durable production) are
documented in `docs/reset-and-rerun.md`; the finding-to-test traceability record
is `docs/phase0-acceptance-spec.md`. Continuous verification runs in
`.github/workflows/ci.yml`.

## Engineering review harness

A cloud-hostable, mobile-responsive **diagnostic dashboard** for remotely
inspecting and validating the engine — a thin HTTP adapter (standard-library
only) *above* the existing API. It contains no reasoning: controllers call
`ReasoningService` / `WorldModelView` and execute the existing artifact modules
(trace, graph, exit test) as the single source of truth.

The authoritative input is a **structured, canonical `EvidenceRecord`** (no
free-text parsing, no NLU). Work is organised into **Test Cases** — deterministic
reasoning experiments; a reviewer adds structured evidence one item at a time,
runs it step-by-step or all at once, inspects the engine's output after each
step, and can reset/rerun, duplicate, and save. It is **not** the product and
must never become the Phase 1 conversation experience.

```bash
python -m sanuvia.adapters.http.server   # then open http://localhost:8000
```

See `docs/review-harness.md` for the full guide (purpose, how it differs from
Phase 1, reviewer workflow, local run), and
`docs/engineering-review-dataset.md` for the official engineering review
dataset — 12 deterministic Test Cases (`D1…D12`) that exercise every major
reasoning behaviour, with machine-verified per-step expected evolution.

**Production deployment** (systemd + Caddy, HTTPS, durable SQLite, backups):
see `docs/deployment.md` and the pre-release `docs/release-checklist.md`. The
deployment is operations-only — it exposes the existing app unchanged and stays
fully deterministic.

## Roadmap (next increments)

1. **Postgres adapter (optional)** — for scaled deployments, behind the same
   ports.
2. **FastAPI transport (optional)** — a richer HTTP adapter over the same
   `ReasoningService` / `WorldModelView` contract, if auto-docs/validation are
   wanted.
# sanuvia
