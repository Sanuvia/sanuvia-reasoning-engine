"""Case 001 fixture integrity + data-driven hypothesis count."""

from __future__ import annotations

from fixtures.longitudinal.case_001 import (
    APPRAISAL_SCRIPT,
    CASE_001,
    HYPOTHESIS_CATALOGUE,
    SPACE,
    SUBJECT,
)
from fixtures.longitudinal.toy_case import build_toy_case

from sanuvia_phase1.conditions import SanuviaPersistentCondition


def test_case_has_six_interactions_including_empty_seq5() -> None:
    assert len(CASE_001.interactions) == 6
    seq5 = CASE_001.interactions[4]
    assert seq5.seq_label == "seq-5"
    assert seq5.evidence == ()  # a real interaction with NO new evidence


def test_anonymisation_note_present() -> None:
    import fixtures.longitudinal.case_001 as mod

    assert mod.__doc__ is not None
    assert "ANONYMISATION NOTE" in mod.__doc__
    assert "Person 1" in mod.__doc__


def test_reliabilities_and_confidences_in_unit_interval() -> None:
    for interaction in CASE_001.interactions:
        for ev in interaction.evidence:
            for value in (
                ev.reliability,
                ev.classification_confidence,
                ev.provenance_confidence,
            ):
                assert 0.0 <= value <= 1.0


def test_appraisal_keys_and_hypotheses_are_defined() -> None:
    engine_ids = {
        ev.engine_id for i in CASE_001.interactions for ev in i.evidence
    }
    catalogue = set(HYPOTHESIS_CATALOGUE)
    for key, appraisal in APPRAISAL_SCRIPT.items():
        assert str(key) in engine_ids  # keyed by a declared engine id
        referenced = (
            set(appraisal.supports)
            | set(appraisal.contradicts)
            | {p.hypothesis_id for p in appraisal.proposals}
        )
        assert referenced <= catalogue  # only defined hypotheses referenced


def test_engine_ids_match_actual_ingestion_order() -> None:
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()
    for interaction in CASE_001.interactions:
        condition.step(interaction)
    state = condition.session_state()
    stored = [str(e.id) for e in state.evidence.list_for_subject(SUBJECT, space_id=SPACE)]
    declared = [ev.engine_id for i in CASE_001.interactions for ev in i.evidence]
    assert stored == declared  # fixture engine_ids reflect real Phase 0 ingestion


def test_infrastructure_is_data_driven_not_hardcoded_to_four() -> None:
    for n in (2, 3, 5):
        case = build_toy_case(n)
        condition = SanuviaPersistentCondition(case)
        condition.start()
        records = [condition.step(i) for i in case.interactions]
        # n hypotheses appear (one per interaction) and are retained through the
        # final hold — with no hard-coded assumption about the count.
        final_hypotheses = {h.hypothesis_id for h in records[-1].hypotheses}
        assert len(final_hypotheses) == n
