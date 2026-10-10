# Phase 1 — Semantic Evaluation Protocol (for approval)

**Status:** APPROVED (Run 001) · **Prepared:** 2026-08-23 · **Updated:** 2026-08-26
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
- The **scoring scale and evaluator process** are **not** defined by the specs;
  they are a governance decision. For Run 001 they are **APPROVED** (0–2 ordinal per
  dimension, no aggregate; two independent evaluators; best-effort blinding) and
  pinned in the governance freeze record (`freeze_record_version 2.0-run001`). None
  of it was set by looking at any results.

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

### Scoring scale — **APPROVED (Run 001)**

The authoritative documents define no numeric scale for these dimensions; the
following scale is a **governance decision, approved for Run 001** and pinned in the
governance freeze record.

Per-dimension ordinal (per condition, per dimension), applied after reading the full
trajectory:

| Level | Meaning |
|---|---|
| 0 — Absent/violation | dimension not exhibited, or a negative-evidence violation occurs |
| 1 — Present but flawed | exhibited but with lapses (e.g. some unsupported continuity) |
| 2 — Present and sound | consistently exhibited per the definition above |

**Handling (approved):** record the level **with a written justification and cited
interactions** for each (level alone is not sufficient). **Do not** aggregate the
five dimensions into a composite score and **do not** derive any pass/fail from these
levels — Phase 1 reports the per-dimension levels with justifications only.

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

This is a protocol decision. For Run 001 the following is **APPROVED** and pinned in
the governance freeze record.

**Approved protocol:**
- **Condition-blind (best-effort):** evaluators see trajectories under **neutral
  condition labels** (no "Sanuvia" / "stateless" / "transcript").
- **Order-randomised:** the presentation order of conditions is randomised per case
  and per evaluator so position carries no signal.
- **Two independent evaluators, then reconciled:** the two evaluators score
  independently before any discussion; disagreements are reconciled with written
  rationale.
- **Recorded limitation:** the Sanuvia condition inevitably exposes richer structure
  (hypotheses, inquiry, uncertainty) which **may reveal its condition identity**;
  blinding is therefore **best-effort only**. Evaluators judge the **content** of
  that structure, not treat its mere presence as a quality signal. **No substantial
  presentation-normalisation layer is added solely to conceal the structure for
  Run 001.**

**Distinction — protocol vs implementation:**
- *Protocol decisions (approved above):* neutral labels, randomisation, two
  independent evaluators, reconciliation, best-effort blinding, recorded limitation.
- *Implementation note:* neutral-labelled, order-randomised per-interaction excerpts
  can be produced from the existing per-condition records; no dedicated
  blinding/normalisation harness is built for Run 001 (no Phase 0 impact).

---

## Approval status (this protocol)

**AUTHORITATIVE / ALREADY AGREED**
- The five evaluation dimensions (continuity, revision, grounding, uncertainty,
  inquiry) and their qualitative definitions, derived from Reasoning Semantics
  v0.2, Eng Spec v0.4 §2.0/§8A, Sys Arch v1.1 §5A, and Programme v1.4 §C.3 / Part 2;
  and the evidence-vs-inference and unsupported-continuity definitions.
- That human evaluation is the primary semantic assessment.

**APPROVED (Run 001)** — pinned in the governance freeze record:
- The 0–2 ordinal scale per dimension, each score with written justification citing
  interactions, **no composite/aggregate** (`semantic_scale`).
- Two independent evaluators with reconciliation (`semantic_evaluators`).
- Neutral labels, randomised order, best-effort blinding, and the recorded
  limitation that Sanuvia structured outputs may reveal condition identity; no
  presentation-normalisation layer for Run 001 (`semantic_blinding`).

**PENDING (non-blocking)**
- Evaluator identities/scheduling and the eval hardware are operational details
  recorded at run time.

*The real evaluation has not been executed.*
