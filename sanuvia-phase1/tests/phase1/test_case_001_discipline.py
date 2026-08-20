"""Case 001 governing discipline: resonance≠accuracy, provenance limits, no
invented evidence, no fixed MD-1 character judgment."""

from __future__ import annotations

from fixtures.longitudinal.case_001 import (
    APPRAISAL_SCRIPT,
    CASE_001,
    HYPOTHESIS_CATALOGUE,
    SPACE,
    SUBJECT,
)

from sanuvia.exit_test.session_state import SessionState

from sanuvia_phase1.conditions import SanuviaPersistentCondition


def _state() -> SessionState:
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()
    for interaction in CASE_001.interactions:
        condition.step(interaction)
    return condition.session_state()


def test_resonance_evidence_er007_supports_nothing() -> None:
    # ER-007 ("I feel better") is appraised as empty and never enters any
    # hypothesis's supporting evidence (Failure Condition 2).
    from sanuvia.domain import EvidenceRecordId

    er007 = APPRAISAL_SCRIPT[EvidenceRecordId("evidence-7")]
    assert er007.supports == () and er007.contradicts == () and er007.proposals == ()

    state = _state()
    for hyp in state.hypotheses.list_for_subject(SUBJECT, space_id=SPACE):
        assert "evidence-7" not in [str(e) for e in hyp.supporting_evidence_ids]


def test_provenance_limited_er006_is_not_asserted_as_support() -> None:
    # ER-006 (partner-referenced, unverified) drives no hypothesis change and is
    # never cited as supporting evidence (Failure Condition 1).
    state = _state()
    for hyp in state.hypotheses.list_for_subject(SUBJECT, space_id=SPACE):
        assert "evidence-6" not in [str(e) for e in hyp.supporting_evidence_ids]


def test_no_invented_evidence() -> None:
    state = _state()
    stored = {str(e.id) for e in state.evidence.list_for_subject(SUBJECT, space_id=SPACE)}
    declared = {ev.engine_id for i in CASE_001.interactions for ev in i.evidence}
    assert stored == declared  # exactly the disclosed evidence — nothing invented


def test_no_fixed_md1_character_judgment() -> None:
    banned = ("bad leader", "obstructive", "incompetent", "toxic", "villain", "at fault")
    texts = [s.lower() for s in HYPOTHESIS_CATALOGUE.values()]
    state = _state()
    for inq in state.inquiries.list_for_subject(SUBJECT, space_id=SPACE):
        texts.append(inq.statement.lower())
    for text in texts:
        for phrase in banned:
            assert phrase not in text
