"""C-5 — coverage fixtures exercised through the real demonstrator infrastructure:
prediction invalidation and failed evidence acquisition."""

from __future__ import annotations

from fixtures.longitudinal.failed_acquisition import (
    CASE_FAILED_ACQUISITION,
    FAILED_ACQUISITION_ENGINE_ID,
    H_ALT_A,
    H_ALT_B,
)
from fixtures.longitudinal.failed_acquisition import SPACE as FA_SPACE
from fixtures.longitudinal.failed_acquisition import SUBJECT as FA_SUBJECT
from fixtures.longitudinal.prediction_invalidation import CASE_PREDICTION_INVALIDATION

from sanuvia_phase1 import demonstrator, metrics
from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.demonstrator import DemonstrationReport
from sanuvia_phase1.language_models import ScriptedLanguageModel


def _conditions(case: object) -> list:  # type: ignore[type-arg]
    n = len(case.interactions)  # type: ignore[attr-defined]
    return demonstrator.build_default_conditions(
        case,  # type: ignore[arg-type]
        ScriptedLanguageModel(("{}",) * n),
        ScriptedLanguageModel(("{}",) * n),
    )


def test_prediction_invalidation_through_demonstrator() -> None:
    conds = _conditions(CASE_PREDICTION_INVALIDATION)
    rep: DemonstrationReport = demonstrator.run(CASE_PREDICTION_INVALIDATION, conds)
    san = list(rep.records_by_condition["sanuvia_persistent"])

    # 5 sequential interactions (Programme v1.4 Part 4A "at least five").
    assert len(san) == 5
    # A prediction forms (seq-2) then is INVALIDATED (seq-3) by a contradiction.
    assert metrics.prediction_count_series(san) == [0, 1, 0, 0, 0]
    assert len(san[1].predictions) == 1
    assert len(san[2].predictions) == 0
    assert any(
        e.outcome == "contradict" and e.affected_object_id == "H_inv"
        for e in san[2].revision_events
    )
    # invalidation is caused by support crossing back below threshold
    support = metrics.support_series(san)["H_inv"]
    assert support[1] is not None and support[1] >= 0.6
    assert support[2] is not None and support[2] < 0.6


def test_failed_acquisition_generates_competing_explanations_not_discarded() -> None:
    conds = _conditions(CASE_FAILED_ACQUISITION)
    rep = demonstrator.run(CASE_FAILED_ACQUISITION, conds)
    san = list(rep.records_by_condition["sanuvia_persistent"])

    assert len(san) == 5
    # After the FAILED_ACQUISITION interaction (seq-2), the engine holds >= two
    # COMPETING candidate explanations — not a single default conclusion.
    ids_after = metrics.hypothesis_ids(san[1])
    assert {H_ALT_A, H_ALT_B} <= ids_after
    assert len({H_ALT_A, H_ALT_B} & ids_after) >= 2

    # The failed-acquisition record is RECORDED (not discarded).
    sanuvia_condition = conds[0]
    assert isinstance(sanuvia_condition, SanuviaPersistentCondition)
    state = sanuvia_condition.session_state()
    stored = {str(e.id) for e in state.evidence.list_for_subject(FA_SUBJECT, space_id=FA_SPACE)}
    assert FAILED_ACQUISITION_ENGINE_ID in stored


def test_coverage_fixtures_are_deterministic() -> None:
    def once(case: object) -> str:
        from sanuvia_phase1 import report

        return report.to_json(demonstrator.run(case, _conditions(case)))  # type: ignore[arg-type]

    for case in (CASE_PREDICTION_INVALIDATION, CASE_FAILED_ACQUISITION):
        assert once(case) == once(case)  # byte-identical replay
