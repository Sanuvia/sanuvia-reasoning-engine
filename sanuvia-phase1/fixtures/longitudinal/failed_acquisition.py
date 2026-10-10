"""Coverage fixture — **failed evidence acquisition** (Programme v1.4 Part 4A:
"At least one case tests failed evidence acquisition").

Authoritative semantics (Engineering Specification §3 / §4.4 — held at v0.2;
Programme v1.4 Part 2 "Six evidence classes, including Failed Acquisition"): a
failed or off-target answer is itself evidence, must **generate competing
candidate explanations, not a single default conclusion, and must not be
discarded**.

Faithful representation through the frozen public API (5 interactions): the
frozen engine does not special-case ``EvidenceClass.FAILED_ACQUISITION`` — it
processes whatever the appraiser returns — so the fixture models the protocol
honestly by (a) classifying the failed acquisition as ``FAILED_ACQUISITION`` and
(b) authoring its appraisal to propose **two competing candidate explanations**
rather than one default. The evidence is recorded by the engine (not discarded).

* seq-1: propose H_base.
* seq-2: a FAILED_ACQUISITION record → proposes H_alt_a AND H_alt_b (competing).
* seq-3: modest support for H_alt_a.
* seq-4: genuine empty hold.
* seq-5: modest support for H_base.
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

SUBJECT: SubjectId = SubjectId("subject-failed-acq")
SPACE = shared_space_id("failed-acquisition")

H_BASE = HypothesisId("H_base")
H_ALT_A = HypothesisId("H_alt_a")
H_ALT_B = HypothesisId("H_alt_b")

# The engine id of the failed-acquisition record (ingestion order): it is the 2nd
# evidence ingested overall.
FAILED_ACQUISITION_ENGINE_ID = "evidence-2"


def _ev(
    ref: str,
    engine_id: str,
    text: str,
    *,
    evidence_class: EvidenceClass = EvidenceClass.REFLECTIVE,
    reliability: float = 0.7,
    role: str = "decision",
) -> CaseEvidence:
    return CaseEvidence(
        ref=ref,
        engine_id=engine_id,
        text=text,
        evidence_class=evidence_class,
        reliability=reliability,
        classification_confidence=0.9,
        provenance_confidence=0.9,
        source="synthetic",
        evidence_role=role,
    )


INTERACTIONS: tuple[CaseInteraction, ...] = (
    CaseInteraction(1, "seq-1", (_ev("FA-001", "evidence-1", "Baseline reflective signal."),)),
    CaseInteraction(
        2, "seq-2",
        (_ev(
            "FA-002", "evidence-2",
            "Off-target / non-answer to the acquisition attempt.",
            evidence_class=EvidenceClass.FAILED_ACQUISITION,
            role="failed_acquisition",
        ),),
    ),
    CaseInteraction(3, "seq-3", (_ev("FA-003", "evidence-3", "Weak support for one candidate."),)),
    CaseInteraction(4, "seq-4", ()),  # genuine hold
    CaseInteraction(5, "seq-5", (_ev("FA-004", "evidence-4", "Weak support for the baseline."),)),
)

APPRAISAL_SCRIPT: dict[EvidenceRecordId, Appraisal] = {
    EvidenceRecordId("evidence-1"): Appraisal(
        proposals=(ProposedHypothesis(H_BASE, "H_base: the initial reading.", 0.4, ()),)
    ),
    # Failed acquisition → COMPETING candidate explanations, not a single default.
    EvidenceRecordId("evidence-2"): Appraisal(
        proposals=(
            ProposedHypothesis(H_ALT_A, "H_alt_a: the answer was withheld (distrust/fatigue).", 0.3, ()),
            ProposedHypothesis(H_ALT_B, "H_alt_b: the question was malformed / off-target.", 0.3, ()),
        )
    ),
    EvidenceRecordId("evidence-3"): Appraisal(supports=(H_ALT_A,)),
    EvidenceRecordId("evidence-4"): Appraisal(supports=(H_BASE,)),
}

CASE_FAILED_ACQUISITION: Case = Case(
    case_id="coverage-failed-acquisition",
    subject_id=SUBJECT,
    space_id=SPACE,
    interactions=INTERACTIONS,
    appraisal_script=APPRAISAL_SCRIPT,
    hypothesis_catalogue={
        H_BASE: "H_base: the initial reading.",
        H_ALT_A: "H_alt_a: the answer was withheld (distrust/fatigue).",
        H_ALT_B: "H_alt_b: the question was malformed / off-target.",
    },
)
