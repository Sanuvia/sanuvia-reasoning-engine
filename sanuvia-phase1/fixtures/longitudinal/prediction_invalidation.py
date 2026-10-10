"""Coverage fixture — **prediction invalidation** (Programme v1.4 Part 4A:
"At least one case requires a prediction to be invalidated").

A focused longitudinal probe (5 sequential interactions) that exercises the real
frozen engine through the public API. It does not fake any Phase-0 behaviour:

* seq-1: propose H_inv at 0.4 (< prediction threshold) — no prediction yet.
* seq-2: support H_inv → crosses the prediction-support threshold → a Prediction
  forms, tied to a model snapshot and the supporting hypothesis.
* seq-3: contradict H_inv → support drops below the threshold → the Prediction
  derived from it is **invalidated** (not carried into the new model version).
* seq-4: genuine empty hold — stays invalidated.
* seq-5: genuine empty hold.

The formation (seq-2) and the invalidating contradiction (seq-3) are adjacent
commit interactions, so the prediction's 1→0 transition is directly attributable
to the contradicting evidence rather than to an intervening hold (holds do not
re-list predictions in the frozen engine).

Numbers are fixture placeholders (like Case 001), outside the frozen
``ReasoningConfig``; the invalidation is produced by the engine's own thresholds,
not asserted into existence.
"""

from __future__ import annotations

from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.domain import (
    EvidenceClass,
    EvidenceRecordId,
    HypothesisId,
    SubjectId,
    shared_space_id,
)

from sanuvia_phase1.case import Case, CaseEvidence, CaseInteraction

SUBJECT: SubjectId = SubjectId("subject-pred-inv")
SPACE = shared_space_id("prediction-invalidation")
H_INV = HypothesisId("H_inv")


def _ev(ref: str, engine_id: str, text: str, reliability: float) -> CaseEvidence:
    return CaseEvidence(
        ref=ref,
        engine_id=engine_id,
        text=text,
        evidence_class=EvidenceClass.REFLECTIVE,
        reliability=reliability,
        classification_confidence=0.9,
        provenance_confidence=0.9,
        source="synthetic",
        evidence_role="decision",
    )


INTERACTIONS: tuple[CaseInteraction, ...] = (
    CaseInteraction(1, "seq-1", (_ev("PI-001", "evidence-1", "Initial signal for H_inv.", 0.8),)),
    CaseInteraction(2, "seq-2", (_ev("PI-002", "evidence-2", "Confirming signal for H_inv.", 0.8),)),
    CaseInteraction(3, "seq-3", (_ev("PI-003", "evidence-3", "Contradicting signal for H_inv.", 0.9),)),
    CaseInteraction(4, "seq-4", ()),  # genuine hold
    CaseInteraction(5, "seq-5", ()),  # genuine hold
)

APPRAISAL_SCRIPT: dict[EvidenceRecordId, Appraisal] = {
    EvidenceRecordId("evidence-1"): Appraisal(
        proposals=(ProposedHypothesis(H_INV, "H_inv: a provisional trajectory hypothesis.", 0.4, ()),)
    ),
    EvidenceRecordId("evidence-2"): Appraisal(supports=(H_INV,)),      # crosses threshold
    EvidenceRecordId("evidence-3"): Appraisal(contradicts=(H_INV,)),  # drops below threshold
}

CASE_PREDICTION_INVALIDATION: Case = Case(
    case_id="coverage-prediction-invalidation",
    subject_id=SUBJECT,
    space_id=SPACE,
    interactions=INTERACTIONS,
    appraisal_script=APPRAISAL_SCRIPT,
    hypothesis_catalogue={H_INV: "H_inv: a provisional trajectory hypothesis."},
)
