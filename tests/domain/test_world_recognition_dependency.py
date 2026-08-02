"""Persistent Understanding, Recognition, and Dependency invariants."""

from __future__ import annotations

import dataclasses

import pytest

from sanuvia.domain import (
    CurrentModelSnapshot,
    DependencyEdge,
    DependencyEdgeId,
    DependencyRelation,
    EvidenceRecordId,
    InvariantViolation,
    ModelUncertainty,
    ObjectRef,
    ReasoningSystemId,
    RecognitionEvent,
    RecognitionEventId,
    RecognitionKind,
    WorldModel,
    WorldModelVersionId,
)
from tests.conftest import SUBJECT, T0


def make_world_model(uncertainty: float = 0.5) -> WorldModel:
    return WorldModel(
        model_version_id=WorldModelVersionId("wm-1"),
        subject_id=SUBJECT,
        reasoning_system_id=ReasoningSystemId("rs-1"),
        model_uncertainty=ModelUncertainty(uncertainty),
        active_hypothesis_ids=(),
        active_prediction_ids=(),
        active_inquiry_ids=(),
        created_at=T0,
    )


def test_world_model_version_is_immutable() -> None:
    model = make_world_model()
    with pytest.raises(dataclasses.FrozenInstanceError):
        model.model_uncertainty = ModelUncertainty(0.9)  # type: ignore[misc]


def test_world_model_carries_aggregate_uncertainty() -> None:
    # FR-PU-002/004: uncertainty is intrinsic to every version.
    assert isinstance(make_world_model().model_uncertainty, ModelUncertainty)


def test_current_snapshot_requires_a_version() -> None:
    with pytest.raises(InvariantViolation):
        CurrentModelSnapshot(
            subject_id=SUBJECT,
            model_version_id=WorldModelVersionId(""),
            committed_at=T0,
        )


def test_recognition_kind_cannot_express_failure() -> None:
    names = {k.name for k in RecognitionKind}
    assert "FAILURE" not in names


def test_recognition_event_must_be_provenance_bound() -> None:
    # FR-RF-004: a recognition must trace to supporting evidence.
    with pytest.raises(InvariantViolation):
        RecognitionEvent(
            id=RecognitionEventId("rec-1"),
            subject_id=SUBJECT,
            kind=RecognitionKind.RECURRING_CYCLE,
            description="a recurring distance/repair cycle",
            supporting_evidence_ids=(),
            model_version_id=WorldModelVersionId("wm-1"),
            created_at=T0,
        )


def test_recognition_event_valid_with_evidence() -> None:
    event = RecognitionEvent(
        id=RecognitionEventId("rec-1"),
        subject_id=SUBJECT,
        kind=RecognitionKind.RECURRING_CYCLE,
        description="a recurring distance/repair cycle",
        supporting_evidence_ids=(EvidenceRecordId("ev-1"),),
        model_version_id=WorldModelVersionId("wm-1"),
        created_at=T0,
    )
    assert event.kind is RecognitionKind.RECURRING_CYCLE


def test_dependency_edge_rejects_self_loop() -> None:
    with pytest.raises(InvariantViolation):
        DependencyEdge(
            id=DependencyEdgeId("dep-1"),
            from_ref=ObjectRef("x"),
            to_ref=ObjectRef("x"),
            relation=DependencyRelation.SUPPORTS,
            created_at=T0,
        )


def test_supersedes_relation_exists_for_evidence_correction() -> None:
    # FR-EM-003: supersession is expressed as an edge, not by mutating evidence.
    assert DependencyRelation.SUPERSEDES.value == "supersedes"
