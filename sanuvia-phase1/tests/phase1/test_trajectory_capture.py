"""Trajectory normalization from both sources."""

from __future__ import annotations

import pytest

from fixtures.longitudinal.case_001 import CASE_001

from sanuvia_phase1 import capture
from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.trajectory import BaselineTurn, ContinuityClaim


def test_sanuvia_record_has_real_engine_fields() -> None:
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()
    record = condition.step(CASE_001.interactions[0])  # seq-1
    assert record.condition == "sanuvia_persistent"
    assert record.ingested_evidence_ids == ("ER-001",)
    assert record.model_uncertainty is not None
    assert record.revision_count is not None and record.revision_count >= 1
    assert record.provenance_traceable is True
    assert record.model_version_id == "wm-1"
    assert record.unsupported_memory_claims == ()
    assert all(h.support is not None for h in record.hypotheses)


def test_parse_baseline_turn_defaults_and_validation() -> None:
    turn = capture.parse_baseline_turn('{"best_explanations": ["x"]}')
    assert turn.best_explanations == ("x",)
    assert turn.competing_hypotheses_held == ()
    assert turn.question_asked is None
    assert turn.continuity_claims == ()

    full = capture.parse_baseline_turn(
        '{"best_explanations": [], "competing_hypotheses_held": '
        '[{"id": "H", "statement": "s"}], "question_asked": "q?", '
        '"continuity_claims": [{"text": "t", "cited_evidence_id": "ER-001"}]}'
    )
    assert full.competing_hypotheses_held[0].hypothesis_id == "H"
    assert full.question_asked == "q?"
    assert full.continuity_claims[0].cited_evidence_id == "ER-001"

    from sanuvia_phase1.failures import MalformedOutputError

    # HARDENED: a non-object reply is malformed output (rejected, not coerced).
    with pytest.raises(MalformedOutputError):
        capture.parse_baseline_turn("[]")  # non-object
    # A present-but-ill-typed field is also malformed (not silently emptied).
    with pytest.raises(MalformedOutputError):
        capture.parse_baseline_turn('{"competing_hypotheses_held": [{"id": "H"}]}')


def test_from_baseline_turn_leaves_engine_fields_none_and_counts_unsupported() -> None:
    interaction = CASE_001.interactions[1]  # seq-2
    turn = BaselineTurn(
        best_explanations=("e",),
        competing_hypotheses_held=(),
        question_asked=None,
        continuity_claims=(
            ContinuityClaim("uncited", None),          # unsupported memory
            ContinuityClaim("cited", "ER-001"),        # supported
        ),
    )
    record = capture.from_baseline_turn(
        "fm_stateless", interaction, ("ER-002", "ER-003"), turn, '{"a": 1}'
    )
    assert record.model_uncertainty is None
    assert record.revision_count is None
    assert record.provenance_traceable is None
    assert record.model_version_id is None
    assert len(record.unsupported_memory_claims) == 1
    assert record.unsupported_memory_claims[0].text == "uncited"
