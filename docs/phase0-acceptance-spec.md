# Phase 0 Acceptance Specification (sanitized)

A versioned, in-repository acceptance record for the Persistent Reasoning Core
(Phase 0). It exists so reviewers can trace each requirement and each reproduced
failure to the code that implements it and the test that verifies it — **without**
publishing any confidential Sanuvia programme document.

> Source-of-truth note. The confidential programme documents are **not** copied
> here. This file records only the *applicable version labels* as they already
> appear in this repository, plus the traceability that maps findings → tests. No
> requirement text is reproduced and no version is invented.

## Applicable sources & versions

Only the labels actually recorded in the repository are listed. Where a document
carries no numeric version in the source material, that is stated explicitly
rather than guessed.

| Source | Version / edition (as recorded) | Role |
|---|---|---|
| Sanuvia Blueprint | **Founding Edition** (no numeric version recorded) | Product philosophy; the reasoning objects. |
| Sanuvia Implementation Programme | **v1.3** | What to build first, and the finish line. |
| Phase 1 Prototype Brief | *no numeric version recorded* (named document) | Phase 0/1 build list and Evaluation Protocol. |
| System Ownership & Runtime Architecture artefacts | *frozen; version not recorded in-repo* | The frozen `FR-*` requirements (families below). |

`FR-*` requirement families realised by the engine (each domain module/port is
annotated with the specific `FR-*` it realises): `FR-EM-001..005`,
`FR-PU-001..005`, `FR-RS-001..005`, `FR-IQ-001..006`, `FR-MR-001..005`,
`FR-RF-001/002/004`.

## Phase 0 acceptance verification

The authoritative Phase 0 proof is the synthetic exit test
(`src/sanuvia/exit_test/`, run with `python -m sanuvia.exit_test`). Its eight
conditions remain the acceptance semantics and are **unchanged** by this
remediation:

1. WorldModel versions are appended, never mutated.
2. Competing hypotheses are retained.
3. Predictions are revised as evidence changes.
4. ModelUncertainty can both increase and decrease.
5. Failed Acquisition produces competing candidate explanations.
6. No InferenceRecord is ever accepted as EvidenceRecord.
7. Every RevisionEvent is traceable to triggering evidence via the ledger.
8. The run is deterministic and reproducible.

## Finding → test traceability

The three reproduced failures from the independent review, plus the Phase 0
acceptance verification and the continuous-verification finding.

| Finding | Requirement / invariant | Implementation | Regression test | CI check | Status |
|---------|--------------------------|----------------|-----------------|----------|--------|
| **1 — Subject/space/actor isolation** | Reasoning is owned by a `(space_id, subject_id)` boundary; `actor_id` is contribution provenance, never a partition key; a repository must never return an entity owned by another subject or space; WorldModel assembly includes only entities of the requested scope; invalid evidence ownership is rejected. (Extends subject scoping FR-PU-001/002.) | `domain/scope.py` (`ReasoningScope`, `SpaceId`, `ActorId`, `DEFAULT_SPACE_ID`); `space_id` on every owned entity + `subject_id` on `Hypothesis`/`Prediction`; scoped repository queries (`in_memory.py`, `sqlite_store.py`); Core Loop ownership gate (`core_loop.py`); scoped `views.py`/`service.py`; SQLite migration (`sqlite_migration.py`). | `tests/test_space_isolation.py` (A–G + rejection, both adapters); `tests/adapters/test_sqlite_migration.py` | *Subject/space isolation*; *Full test suite* | ✅ Closed |
| **2 — Durable SQLite reset/rerun** | A deterministic Test Case rerun must not collide on ids; the test harness may reset a scratch database; durable production reasoning is collision-safe and never reset-erased; test-only deterministic id generators are not used for durable operation. | `SqliteReasoningStore.reset()`; durable wiring defaults to `UuidGenerator`/`SystemClock` (`wiring.py`); harness clears the DB on rebuild (`testcase.py`); documented in `docs/reset-and-rerun.md`. | `tests/adapters/test_sqlite_reset_rerun.py` (reproduces the original failure, then proves the fix + durability) | *SQLite reset/rerun*; *Full test suite* | ✅ Closed |
| **3 — Deployment** | A clean host can obtain the repo, load example config (no secrets), install, initialise persistence, start, health-check, and run the Phase 0 verification; deployment references the active repository. | Safe `/.env.example` (placeholders only); repo refs → `Sanuvia/sanuvia-reasoning-engine` (`deploy/sanuvia.service`, `docs/deployment.md`); `scripts/smoke.sh`; `/health` returns `{status, version, backend}`. | `tests/test_clean_host_smoke.py`; `scripts/smoke.sh` | *Deployment smoke (python)*; *Deployment smoke (shell)* | ✅ Closed |
| **4 — Continuous verification** | Every commit runs the suite, type checks, the exit test, and the isolation/reset/deployment regressions from a clean checkout. | `.github/workflows/ci.yml` (matrix py3.11/py3.12). | (the workflow runs all tests) | *all CI jobs* | ✅ Added |
| **Phase 0 acceptance** | The eight synthetic exit-test conditions hold; reasoning is deterministic and byte-identical for valid single-subject scenarios. | `src/sanuvia/exit_test/` (unchanged semantics). | `tests/test_exit_test.py`; `python -m sanuvia.exit_test` | *Phase 0 exit test* | ✅ Passing |

## What did NOT change

- The reasoning engine's Core Loop and Model Revision **semantics** — support
  arithmetic, thresholds, disposition-by-reliability, versioning, prediction
  grounding, inquiry selection — are untouched. `space_id`/`subject_id` are
  ownership metadata; they never enter the reasoning math.
- The exit-test **acceptance semantics** are unchanged; the canonical proof still
  passes byte-identically.
- No Phase 1 work, no natural-language/LLM functionality, and no product/UI
  features were added.
