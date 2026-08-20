"""Case 001 — Leadership Trajectory & Organisational Misalignment.

fixtures/longitudinal/case-001-leadership-trajectory
Referenced from: Sanuvia Implementation Programme, Part 4, Section C (Case Registry).

ANONYMISATION NOTE (must stay attached wherever this fixture is copied):
This case is drawn from a real personal conversation. The case subject is
referred to throughout as **Person 1**, not by name. Colleagues are referred to
by role only (MD-1, ED-A, ED-B, "engineering and product colleagues"); the
employer is "the organisation". No names or identifying details beyond role are
retained.

------------------------------------------------------------------------------
DISCIPLINE ENCODED HERE (see docs/phase1-controlled-demonstrator.md)
------------------------------------------------------------------------------
* Observation vs interpretation — ``CaseEvidence.text`` carries only the fixture
  "Observation"; a participant's *interpretation* is never ingested as evidence.
* Resonance ≠ accuracy — ER-007 ("I feel better") is appraised as **nothing**; it
  never strengthens an accuracy hypothesis (Failure Condition 2).
* Provenance limits — ER-006 (partner-referenced, unverified) is low reliability /
  low provenance and is appraised as **nothing**; it is never asserted as
  system-observed (Failure Condition 1).
* Retain competing hypotheses — H1–H4 are proposed only where the fixture (§5)
  attributes their supporting evidence; none is dropped. "Silence is not
  disconfirmation": a hypothesis with no contradicting evidence keeps its support.
* Do NOT engineer the inquiry — appraisal supports are authored strictly from the
  fixture's §5 evidence lists; support values are **not** tuned to make H1/H4 the
  engine's top-two inquiry pair. Whatever pair the frozen engine selects is
  recorded as the observed result.

------------------------------------------------------------------------------
AUTHORING CHOICES (flagged (B) — implementation choices, reviewable)
------------------------------------------------------------------------------
* (B) Reliability floats: High=0.8, Medium=0.5, Low-med=0.35 — placeholders that
  live *outside* the frozen ``ReasoningConfig``.
* (B) Proposal initial support = 0.4 (0.3 for the untested H4), following the
  Phase-0 exit-test convention for competing proposals.
* (B) H4 introduction point: the fixture does not pin H4 to a single ER (its
  support is the diffuse single-evening cluster). H4 is introduced conservatively
  at ER-005 (the ambiguous 2026/2027 framing that H1 reads as development and H4
  reads as reactive exhaustion), with low support and no boosting — it stays
  "untested, not disconfirmed".
* (B) ER-003 is decision/emotional-salience and the fixture forbids reading it as
  accuracy; §5 lists it as supporting no hypothesis, so its appraisal is empty.
"""

from __future__ import annotations

from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.domain import (
    EvidenceClass,
    EvidenceRecordId,
    HypothesisId,
    SubjectId,
    personal_space_id,
)

from sanuvia_phase1.case import Case, CaseEvidence, CaseInteraction

# -- scope ---------------------------------------------------------------------
SUBJECT: SubjectId = SubjectId("person-1")
SPACE = personal_space_id("person-1")

# -- hypothesis catalogue (statements are the fixture §5 statements) -----------
H1 = HypothesisId("H1_developmental_transition")
H2 = HypothesisId("H2_organisational_misalignment")
H3 = HypothesisId("H3_anticipatory_protection")
H4 = HypothesisId("H4_temporary_exhaustion")

HYPOTHESIS_CATALOGUE: dict[str, str] = {
    H1: "Person 1 has substantially completed a leadership-validation phase and is "
    "moving toward a creation-oriented phase.",
    H2: "The current environment does not provide the governance conditions or "
    "developmental trajectory Person 1 wants, independent of any single relationship.",
    H3: "The exit narrative partly protects against the emotional cost of a possible "
    "promotion rejection.",
    H4: "Current workplace strain is temporarily amplifying the desire to leave and "
    "build elsewhere, and may recede.",
}


def _ev(
    ref: str,
    engine_id: str,
    text: str,
    *,
    evidence_class: EvidenceClass = EvidenceClass.REFLECTIVE,
    reliability: float = 0.8,
    classification_confidence: float = 0.9,
    provenance_confidence: float = 0.9,
    role: str = "decision",
) -> CaseEvidence:
    return CaseEvidence(
        ref=ref,
        engine_id=engine_id,
        text=text,
        evidence_class=evidence_class,
        reliability=reliability,
        classification_confidence=classification_confidence,
        provenance_confidence=provenance_confidence,
        source="direct reflection (transcript)",
        evidence_role=role,
    )


# -- evidence (RawObservation text only; ingestion order fixes engine ids) ------
ER001 = _ev(
    "ER-001", "evidence-1",
    "Person 1 states that a 'No' on promotion will be used to plan their exit, "
    "citing lack of growth.",
    role="decision",
)
ER002 = _ev(
    "ER-002", "evidence-2",
    "Person 1 states that they and MD-1, along with a few other MDs, do not share "
    "the same view of how the organisation should be governed.",
    role="accuracy",
)
ER003 = _ev(
    "ER-003", "evidence-3",
    "Person 1 states they do not want to spend another year proving their worth.",
    role="decision",
)
ER004 = _ev(
    "ER-004", "evidence-4",
    "Person 1 compares themself to ED-A and ED-B at a comparable level; ED-B has "
    "built stakeholder trust, while Person 1 has been the foundation stakeholders "
    "use to drive decisions.",
    reliability=0.5, role="accuracy-candidate-unverified",
)
ER005 = _ev(
    "ER-005", "evidence-5",
    "Person 1 states: 2026 was about proving their leadership; 2027 is about "
    "building and establishing it. They anticipate another promotion cycle would "
    "feel repetitive, not developmental.",
    role="primary-support-H1",
)
ER006 = _ev(
    "ER-006", "evidence-6",
    "Conversational partner refers to Person 1 having built delivery and resource "
    "plans and produced analysis senior leaders used to make decisions, attributed "
    "to earlier sessions (not independently verified in this transcript).",
    evidence_class=EvidenceClass.NARRATIVE,
    reliability=0.35, classification_confidence=0.6, provenance_confidence=0.3,
    role="accuracy-provenance-limited",
)
ER007 = _ev(
    "ER-007", "evidence-7",
    "Person 1 states 'perfect, I feel better' following the reframing of the "
    "promotion decision as directional rather than evaluative.",
    role="resonance",
)
ER008 = _ev(
    "ER-008", "evidence-8",
    "Person 1 states they do not need to shrink to silence to avoid upsetting an "
    "MD; affirms they listen, adapt and learn; states they do not expect MDs' "
    "reasoning to always make sense to them.",
    role="decision/accuracy",
)

# -- interactions (ALL SIX seq positions; seq 5 is a genuine empty hold) --------
INTERACTIONS: tuple[CaseInteraction, ...] = (
    CaseInteraction(1, "seq-1", (ER001,)),
    CaseInteraction(2, "seq-2", (ER002, ER003)),
    CaseInteraction(3, "seq-3", (ER004,)),
    CaseInteraction(4, "seq-4", (ER005, ER006)),
    CaseInteraction(5, "seq-5", ()),  # REAL interaction, NO new evidence — must hold
    CaseInteraction(6, "seq-6", (ER007, ER008)),
)

# -- authored appraisal script (keyed by Phase-0 engine ids) -------------------
# Each entry is derived ONLY from the fixture §5 evidence lists + role discipline.
APPRAISAL_SCRIPT: dict[EvidenceRecordId, Appraisal] = {
    EvidenceRecordId("evidence-1"): Appraisal(
        proposals=(ProposedHypothesis(H3, HYPOTHESIS_CATALOGUE[H3], 0.4, ()),),
    ),
    EvidenceRecordId("evidence-2"): Appraisal(
        proposals=(ProposedHypothesis(H2, HYPOTHESIS_CATALOGUE[H2], 0.4, ()),),
    ),
    # ER-003: decision/emotional-salience; §5 lists it as supporting no hypothesis,
    # and the fixture forbids reading it as accuracy -> recorded, no change.
    EvidenceRecordId("evidence-3"): Appraisal(),
    EvidenceRecordId("evidence-4"): Appraisal(supports=(H2,)),
    EvidenceRecordId("evidence-5"): Appraisal(
        proposals=(
            # H1 primary support; cite ER-001 too (building-orientation recurs
            # across ER-001 and ER-005) to preserve provenance without proposing
            # H1 before its basis exists.
            ProposedHypothesis(
                H1, HYPOTHESIS_CATALOGUE[H1], 0.4,
                (EvidenceRecordId("evidence-1"),),
            ),
            # H4 introduced conservatively (untested), low support, no boosting.
            ProposedHypothesis(H4, HYPOTHESIS_CATALOGUE[H4], 0.3, ()),
        ),
        # ER-005's independent building enthusiasm is weak evidence AGAINST pure
        # anticipatory protection (fixture H3 disconfirming/missing).
        contradicts=(H3,),
    ),
    # ER-006: provenance-limited inherited claim; never asserted as observed.
    EvidenceRecordId("evidence-6"): Appraisal(),
    # ER-007: resonance only; never strengthens an accuracy hypothesis.
    EvidenceRecordId("evidence-7"): Appraisal(),
    EvidenceRecordId("evidence-8"): Appraisal(supports=(H1,)),
}

CASE_001: Case = Case(
    case_id="case-001-leadership-trajectory",
    subject_id=SUBJECT,
    space_id=SPACE,
    interactions=INTERACTIONS,
    appraisal_script=APPRAISAL_SCRIPT,
    hypothesis_catalogue=HYPOTHESIS_CATALOGUE,
)
