"""A tiny synthetic case with a configurable number of hypotheses.

Its only purpose is to prove the Phase 1 infrastructure is **data-driven**: it
carries ``n`` hypotheses (not four), and the demonstrator/metrics handle it
without any hard-coded assumption about the hypothesis count.
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


def build_toy_case(n_hypotheses: int) -> Case:
    """Build a case that introduces ``n_hypotheses`` distinct hypotheses, one per
    interaction, plus a final empty 'hold' interaction."""
    if n_hypotheses < 1:
        raise ValueError("n_hypotheses must be >= 1")

    subject = SubjectId("toy-subject")
    space = shared_space_id("toy")
    catalogue: dict[str, str] = {
        f"H{i}_toy": f"Toy hypothesis number {i}." for i in range(1, n_hypotheses + 1)
    }

    interactions: list[CaseInteraction] = []
    script: dict[EvidenceRecordId, Appraisal] = {}
    for i in range(1, n_hypotheses + 1):
        engine_id = f"evidence-{i}"
        ev = CaseEvidence(
            ref=f"TE-{i:03d}",
            engine_id=engine_id,
            text=f"Toy observation {i}.",
            evidence_class=EvidenceClass.REFLECTIVE,
            reliability=0.7,
            classification_confidence=0.9,
            provenance_confidence=0.9,
            source="synthetic",
            evidence_role="decision",
        )
        interactions.append(CaseInteraction(i, f"seq-{i}", (ev,)))
        hid = HypothesisId(f"H{i}_toy")
        script[EvidenceRecordId(engine_id)] = Appraisal(
            proposals=(ProposedHypothesis(hid, catalogue[hid], 0.4, ()),)
        )
    # final genuine hold
    interactions.append(CaseInteraction(n_hypotheses + 1, f"seq-{n_hypotheses + 1}", ()))

    return Case(
        case_id=f"toy-{n_hypotheses}",
        subject_id=subject,
        space_id=space,
        interactions=tuple(interactions),
        appraisal_script=script,
        hypothesis_catalogue=catalogue,
    )
