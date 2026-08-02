# Phase 0 — Design Notes

Short notes on the deliberate scaffolding and guarantees of the Persistent
Reasoning Core. These record *intent* so reviewers don't mistake a Phase-0
stand-in for a product algorithm.

## 1. How `ScriptedAppraiser` produces candidate hypotheses

`ScriptedAppraiser` does **not generate** hypotheses — it performs no inference.
It is a deterministic lookup: given an `EvidenceRecord`, it returns a pre-authored
`Appraisal` keyed by the record's id. The `Appraisal` is where the *scenario
author* declares, for that evidence:

- which existing hypotheses it **supports** (by lineage id),
- which it **contradicts**,
- which new candidate explanations it **proposes** (`ProposedHypothesis`: lineage
  id, statement, initial support, and an optional trajectory hint).

Candidate-hypothesis *generation* is a language-understanding task, which the
architecture assigns to the foundation model ("FM generates candidate inferences;
Sanuvia manages hypotheses and revises models"). Phase 0 excludes the FM, so
generation is supplied by the scenario. A later phase swaps in an FM-backed
`EvidenceAppraiser` behind the same port with **no change to the reasoning
engine**, which manages, scores, and revises whatever candidates it receives.

Implication: the exit test proves the engine *reasons over* candidates
persistently — not that it *discovers* them.

## 2. `ReasoningConfig` values are Phase-0 placeholders

Every number in `application/reasoning/config.py` is a **placeholder**, not a
calibrated or specified value:

| Field | Placeholder role |
|---|---|
| `support_learning_rate` | how fast support moves per observation |
| `established_support_threshold` | when a contradiction counts as an anomaly |
| `contradiction_revise_reliability` / `contradiction_reject_reliability` | stand-in for the deferred assumption-selection logic (REVISE / ESCALATE / REJECT) |
| `prediction_support_threshold` | when a hypothesis yields (or loses) a prediction |
| `inquiry_uncertainty_threshold` | when material uncertainty raises an inquiry |

They are collected in one immutable, injectable object so they read as tunable
policy, not magic numbers, and can be replaced without touching the reasoning
structure. **None** of them implements a deferred transition function — those are
not implemented at all.

## 3. `PlaceholderCommitAllPolicy` is a temporary scaffold

The `proposed → committed` transition governance (FR-MR-003) is **intentionally
unspecified** by the frozen spec ("what decides or validates the transition is
not resolved by PRS text"). `PlaceholderCommitAllPolicy` commits every proposed
event so the exit test can exercise revision. It is:

- named to make its placeholder nature unmistakable at every call site,
- located in the adapter layer (never inside the engine),
- reached only through the `RevisionCommitPolicy` port.

When the governance is specified, replace this adapter; the engine, which only
*asks* the port, is unaffected.

## 4. Determinism & reproducibility

The reasoning engine is **fully deterministic**. Given the same inputs it
produces byte-identical results, so the synthetic exit test is reproducible:

- No wall-clock or randomness in the domain or engine. Time comes from the
  `Clock` port; ids from the `IdGenerator` port. Tests/harness use `ManualClock`
  and `SequentialIdGenerator` — both deterministic.
- No `set` iteration affects output ordering; ordered `dict`s and stable `sorted`
  are used throughout. `_dedup` preserves first-seen order.
- The `ScriptedAppraiser` is a pure keyed lookup.
- The `PlaceholderCommitAllPolicy` is pure.

This is asserted by `tests/reasoning/test_determinism.py`, which runs the same
scenario twice and checks the version ids, uncertainties, ledger, and predictions
are identical.
