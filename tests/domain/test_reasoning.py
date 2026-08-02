"""Hypothesis and Prediction invariants (FR-RS-001 .. FR-RS-005)."""

from __future__ import annotations

import pytest

from sanuvia.domain import (
    EvidenceRecordId,
    FutureTrajectory,
    HypothesisId,
    InvariantViolation,
    Prediction,
    PredictionId,
    PredictionLikelihood,
    TrajectoryKind,
    WorldModelVersionId,
)
from tests.conftest import T0, make_hypothesis


def test_hypothesis_rejects_evidence_that_both_supports_and_contradicts() -> None:
    with pytest.raises(InvariantViolation):
        make_hypothesis(supporting=("ev-1",), contradicting=("ev-1",))


def test_hypothesis_has_no_lifecycle_status_field() -> None:
    # The frozen spec defines no status enum for Hypothesis (unlike Inquiry).
    import dataclasses

    field_names = {f.name for f in dataclasses.fields(make_hypothesis())}
    assert "status" not in field_names


def test_hypothesis_support_is_mandatory_and_attached() -> None:
    # FR-RS-005: uncertainty is never omitted. It is a required constructor arg.
    hypothesis = make_hypothesis(support=0.3)
    assert hypothesis.support.value == 0.3


def test_trajectory_kinds_cannot_express_failure() -> None:
    # No relationship-failure predictions, ever (FR-RF-002 / Programme Part 2).
    names = {k.name for k in TrajectoryKind}
    assert "FAILURE" not in names
    assert names == {
        "OBSERVED_TRAJECTORY",
        "RECURRING_CYCLE",
        "FREQUENCY_CHANGE",
        "INTERRUPTION_OPPORTUNITY",
    }


def _make_prediction(*, hyps: tuple[str, ...], evs: tuple[str, ...]) -> Prediction:
    return Prediction(
        id=PredictionId("pred-1"),
        trajectory=FutureTrajectory(
            kind=TrajectoryKind.RECURRING_CYCLE, description="distance-then-repair cycle"
        ),
        likelihood=PredictionLikelihood(0.6),
        derived_from_hypothesis_ids=tuple(HypothesisId(h) for h in hyps),
        derived_from_evidence_ids=tuple(EvidenceRecordId(e) for e in evs),
        model_version_id=WorldModelVersionId("wm-1"),
        created_at=T0,
    )


def test_prediction_must_be_traceable_to_hypothesis_or_evidence() -> None:
    with pytest.raises(InvariantViolation):
        _make_prediction(hyps=(), evs=())


def test_prediction_may_derive_from_multiple_hypotheses() -> None:
    # FR-RS-004 cites "Hypotheses" (plural); a single originating hypothesis is
    # not required, and the WorldModel-only case (evidence, no hypothesis) is
    # left open — both are constructible.
    pred = _make_prediction(hyps=("hyp-1", "hyp-2"), evs=())
    assert len(pred.derived_from_hypothesis_ids) == 2

    pred2 = _make_prediction(hyps=(), evs=("ev-1",))
    assert pred2.derived_from_evidence_ids == (EvidenceRecordId("ev-1"),)
