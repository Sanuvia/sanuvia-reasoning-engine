# Phase 1 — Semantic Evaluation Protocol (for approval)

**Status:** DRAFT — pending protocol approval · **Prepared:** 2026-08-23
**Parent:** [Experiment Manifest](phase1-experiment-manifest.md) (this is §10–§11)

This protocol defines the **human** semantic evaluation that accompanies the Phase 1
run. The experiment protocol specifies that human evaluation separately assesses
semantic hypothesis continuity/revision, uncertainty, and inquiry quality — the code
records raw observables, humans judge meaning.

**Governance boundary (read first).** The authoritative documents (System
Architecture v1.1; Engineering Specification v0.4; Reasoning Semantics v0.2;
Implementation Programme v1.4) define *what* is reasoned about (evidence vs
inference, hypotheses, uncertainty, inquiry, prediction) and *which* observables
matter (Programme §C.3). They **do not define a numeric scoring scale, weighting,
or pass/fail threshold** for semantic quality. Therefore:

- The **dimensions**, and the definitions of positive/negative evidence, valid
  revision, and unsupported continuity below, are **derived from the authoritative
  documents** and are offered as authoritative-aligned structure.
- Every **numeric scale, aggregate, or decision rule** is presented **only** as
  **PROPOSED — REQUIRES APPROVAL**. Nothing numeric here is a
  requirement, and none of it was set by looking at any results.

---

## 10. Semantic evaluation rubric

### Common evaluator setup

- **Unit of evaluation:** one condition's longitudinal trajectory over Case 001
  (`seq-1 … seq-6`), presented interaction-by-interaction.
- **What the evaluator sees (per interaction):** the interaction's raw input; the
  condition's output for that turn (its hypotheses/answer, any question asked, any
  stated uncertainty, any continuity claim); and, for the Sanuvia condition, the
  surfaced structured fields (hypotheses with supporting/contradicting evidence,
  inquiry + status, uncertainty, predictions, revision events, dependency edges).
  Evaluators also see the **evidence actually disclosed** up to that turn, so they
  can check grounding.
- **What the evaluator does NOT see:** which condition produced the trajectory (see
  §11, if blinding is approved).
- **Golden reference:** none is imposed. Evaluators judge against the disclosed
  evidence and the definitions below, **not** against a pre-set "correct" answer —
  consistent with Case 001's rule that there is no fixed adverse character verdict.

### A. Hypothesis continuity

- **Definition (authoritative-aligned):** the same reading is *carried across
  interactions as the same commitment*, rather than re-invented each turn
  (Programme §C.3 "retained/revised/dropped vs re-derived"; Sys Arch v1.1 §5A —
  persistent, status-bearing objects).
- **Positive evidence:** a hypothesis persists across turns as the *same*
  commitment and its grounding accumulates (e.g. earlier evidence remains cited as
  later evidence is added).
- **Negative evidence:** a fresh, differently-framed reading each turn with no
  carried commitment (re-derivation); or a claim of continuity the content does not
  support.
- **Unsupported continuity (critical):** a continuity claim ("as you said earlier
  …") with **no cited evidence** for the referenced content — i.e. asserting memory
  that is not grounded. In the observables this is a continuity claim with
  `cited_evidence_id = null` (unsupported-memory signal).
- **Illustrative example (Case 001, from the fixture):** a durable "H1"-type reading
  that stays the same commitment while accumulating support across turns is genuine
  continuity; a transcript-baseline line such as *"as you have said throughout …"*
  with no cited evidence is **unsupported** continuity.

### B. Hypothesis revision

- **Definition (authoritative-aligned):** a *justified change* to a held commitment
  triggered by new evidence — strengthen / weaken / add / drop — with the change
  traceable to the evidence that caused it (Sys Arch v1.1 §5A recursive revision;
  Reasoning Semantics v0.2 evidence→model change).
- **Valid revision:** a change to a hypothesis (support up/down, added, retired,
  or contradicted) that is **triggered by and cites specific new evidence**, and
  that preserves separately-tracked contradiction rather than silently overwriting
  it.
- **Negative evidence:** a change with no evidential trigger (drift); collapsing a
  contradiction into agreement; or "revising" by discarding a prior commitment
  without cause.
- **Illustrative example (Case 001):** when contradicting evidence arrives for an
  anticipatory-protection reading, weakening that hypothesis *and recording the
  contradiction against it* is a valid revision; changing the story with no cited
  trigger is not.

### C. Evidence grounding

- **Definition (authoritative — Reasoning Semantics v0.2; Programme v1.4 Part 2):**
  **evidence and inference are distinct.** Claims must rest on **observations**
  ("the person said/did X"), not on inferences dressed as facts, and provenance
  must be traceable.
- **Positive evidence:** each asserted reading is tied to specific disclosed
  observations; unverified/second-hand material is treated cautiously, not as
  established; provenance is intact.
- **Negative evidence:** asserting an inference as observed fact; citing evidence
  that was never disclosed (fabrication); treating **resonance** ("I feel better")
  as if it confirmed a hypothesis; or treating **unverified, partner-referenced**
  material as established support.
- **Illustrative examples (Case 001, encoded in the fixture discipline):** `ER-007`
  ("I feel better") is resonance and must support **no** hypothesis; `ER-006`
  (partner-referenced, unverified) must **not** be cited as support. Using either as
  grounding is negative evidence.

### D. Uncertainty handling

- **Definition (authoritative-aligned — Eng Spec v0.4 §2.0 six uncertainty types
  incl. PredictionLikelihood):** the system represents and communicates *what it
  does not yet know*, appropriately to the evidence.
- **Positive evidence:** uncertainty is flagged where the evidence is genuinely
  thin or conflicting, and narrows as evidence accumulates; competing readings are
  held open rather than prematurely collapsed.
- **Negative evidence:** false confidence on thin evidence; or uniform,
  content-free hedging that never resolves.
- **Comparability caveat:** only the Sanuvia condition exposes a structured
  World-Model uncertainty value; baselines may only express uncertainty in prose.
  Evaluators judge **appropriateness**, not a numeric comparison of the two
  (structurally non-comparable — §9 of the manifest).

### E. Inquiry quality

- **Definition (authoritative-aligned — Eng Spec v0.4 §8A / Sys Arch v1.1 §5A
  Inquiry as a persistent, status-bearing object; Programme §C.3 "the next question
  the system asks"):** the question the system raises is the one most useful to
  resolve a *specific, world-model-attributable* uncertainty.
- **Positive evidence:** a question that targets a genuine open point between
  competing readings and would, if answered, change the model; sensible status
  progression over turns (e.g. proposed → active → resolved) where applicable.
- **Negative evidence:** generic reassurance or a re-explain prompt that resolves
  nothing; a question unrelated to any held uncertainty.
- **Note:** targeted inquiry *selection* (optimal EIG) is a deferred Phase-0
  capability; evaluators judge the inquiry that is actually surfaced, not an ideal
  the engine does not yet compute.

### Scoring scale — **PROPOSED — REQUIRES APPROVAL**

> The authoritative documents define **no** numeric scale for these dimensions.
> The following is a **minimal candidate only**, offered to unblock approval. It is
> **not** an authoritative requirement and must not be treated as one. Governance
> may instead choose purely qualitative notes with no numbers.

Missing governance decision: *the scoring scale, any aggregation across dimensions,
and any decision threshold.*

**PROPOSED** minimal per-dimension ordinal (per condition, per dimension), applied
after reading the full trajectory:

| Level | Meaning |
|---|---|
| 0 — Absent/violation | dimension not exhibited, or a negative-evidence violation occurs |
| 1 — Present but flawed | exhibited but with lapses (e.g. some unsupported continuity) |
| 2 — Present and sound | consistently exhibited per the definition above |

**PROPOSED** handling: record the level **with a written justification and cited
interactions** for each (level alone is not sufficient). **Do not** aggregate into a
single score and **do not** derive any pass/fail from these levels in Phase 1 — any
aggregation/threshold is a separate governance decision (manifest §12). If
governance prefers, replace the 0–2 scale entirely with free-text findings.

### Evaluator instructions (procedure)

1. Read the whole trajectory before scoring; judge longitudinally, not per turn in
   isolation.
2. For each dimension, cite the specific interactions that justify your assessment.
3. Ground every judgement in the **disclosed evidence**; flag any claim that is not
   grounded (unsupported continuity / fabricated or misused evidence).
4. Do not reward fluency, confidence, or narrative neatness per se; reward correct
   grounding, justified revision, and appropriate uncertainty.
5. Do not infer or record which system produced the trajectory (see §11).
6. Where you cannot judge (e.g. a deferred capability), record "not applicable /
   not computed", never a fabricated judgement.

---

## 11. Blindness / evaluator protection

**This is a protocol decision, not (yet) an implementation requirement.** The
authoritative documents do not mandate a specific blinding procedure; the following
is **PROPOSED — REQUIRES APPROVAL** and is recommended good practice.

**PROPOSED protocol:**
- **Condition-blind:** evaluators see trajectories with condition identity removed
  (no "Sanuvia" / "stateless" / "transcript" labels), under neutral labels.
- **Order-randomised:** the presentation order of conditions is randomised per case
  and per evaluator so position carries no signal.
- **Independent then reconciled:** at least two evaluators score independently
  before any discussion; disagreements are reconciled with written rationale.
  *(Evaluator count is a governance decision — PENDING.)*
- **No leakage of structured internals as identity:** the Sanuvia condition
  inevitably exposes richer structure (hypotheses, inquiry, uncertainty), which can
  reveal its identity. Evaluators should judge the **content** of that structure,
  not treat its mere presence as a quality signal; alternatively governance may
  choose a presentation that normalises surface form across conditions.

**Distinction — protocol vs implementation:**
- *Protocol decisions (this document):* whether to blind, how many evaluators,
  randomisation, reconciliation.
- *Implementation requirements (only if the above is approved):* a small,
  additive Phase-1 reporting mode that emits **condition-blinded, order-randomised**
  per-interaction excerpts for evaluators. The report layer already produces
  per-condition records and can render blinded excerpts; building a dedicated
  blinding/export harness is **out of scope until the protocol is approved** and
  would be a separate, additive change (no Phase 0 impact).

---

## Approval status (this protocol)

**AUTHORITATIVE / ALREADY AGREED**
- The five evaluation dimensions (continuity, revision, grounding, uncertainty,
  inquiry) and their qualitative definitions, derived from Reasoning Semantics
  v0.2, Eng Spec v0.4 §2.0/§8A, Sys Arch v1.1 §5A, and Programme v1.4 §C.3 / Part 2;
  and the evidence-vs-inference and unsupported-continuity definitions.
- That human evaluation is the primary semantic assessment.

**PENDING APPROVAL / GOVERNANCE**
- The scoring scale (or a decision to use qualitative notes only); any cross-
  dimension aggregation; the number of evaluators and the reconciliation process;
  whether/how blinding is operationalised.

**PROPOSED (NOT YET APPROVED)**
- The 0–2 ordinal scale and its "record with justification, do not aggregate"
  handling; the condition-blind, order-randomised, two-independent-evaluator
  procedure in §11.

**BLOCKING BEFORE REAL RUN**
- Governance must approve either (a) this rubric with a chosen scale, or (b) an
  explicit qualitative-only rubric, before the human evaluation can proceed. This is
  independent of, and additional to, the model-availability and C.4/C.5 blockers in
  the manifest.

*The real evaluation has not been executed.*
