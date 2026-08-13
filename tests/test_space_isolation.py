"""Finding 1 — subject / space / actor isolation (negative regression tests).

These demonstrate ATTEMPTED leakage and prove it fails: an entity owned by one
(space, subject) is never returned for another. They cover the reviewer's matrix:

    A. two subjects in the same space
    B. the same subject in two different spaces
    C. Personal vs Shared spaces
    D. two unrelated Shared spaces
    E. hypotheses crossing boundaries
    F. predictions crossing boundaries
    G. WorldModel assembly crossing boundaries
    + invalid evidence ownership is rejected

The repository-level tests run against BOTH persistence adapters (in-memory and
SQLite) so the invariant holds wherever state lives.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.domain import (
    DEFAULT_SPACE_ID,
    CurrentModelSnapshot,
    EvidenceClass,
    EvidenceRecordId,
    HypothesisId,
    InvariantViolation,
    ModelUncertainty,
    ObjectRef,
    ReasoningScope,
    ReasoningSystemId,
    RevisionEvent,
    RevisionEventId,
    RevisionOutcome,
    RevisionStatus,
    SpaceId,
    SubjectId,
    WorldModel,
    WorldModelVersionId,
    personal_space_id,
    shared_space_id,
)
from tests.conftest import T0, make_hypothesis, make_prediction

# Distinct scopes used throughout.
SPACE = DEFAULT_SPACE_ID
PERSONAL = personal_space_id("alice")
SHARED_1 = shared_space_id("team-one")
SHARED_2 = shared_space_id("team-two")
A = SubjectId("subject-A")
B = SubjectId("subject-B")


StoreFactory = Callable[[], Any]


@pytest.fixture(params=["memory", "sqlite"])
def store(request: Any) -> Any:
    if request.param == "memory":
        return InMemoryReasoningStore()
    return SqliteReasoningStore(":memory:")


# ===========================================================================
# Repository-level attempted leakage (E, F, G, A, B) on BOTH adapters
# ===========================================================================


def test_hypothesis_does_not_leak_across_subjects(store: Any) -> None:
    """A. two subjects, same space — E. hypotheses crossing boundaries."""
    store.hypotheses.add(make_hypothesis(hypothesis_id="H_A", subject_id=A))
    store.hypotheses.add(make_hypothesis(
        record_id="rec-b", hypothesis_id="H_B", subject_id=B))

    a_ids = [h.hypothesis_id for h in store.hypotheses.list_for_subject(A)]
    b_ids = [h.hypothesis_id for h in store.hypotheses.list_for_subject(B)]
    assert a_ids == ["H_A"]
    assert b_ids == ["H_B"]  # would be ["H_A", "H_B"] under the old leak


def test_hypothesis_does_not_leak_across_spaces(store: Any) -> None:
    """B. same subject, two spaces — same hypothesis id, isolated by space."""
    store.hypotheses.add(make_hypothesis(
        record_id="rec-1", hypothesis_id="H_shared", subject_id=A, space_id=SHARED_1,
        support=0.9))
    store.hypotheses.add(make_hypothesis(
        record_id="rec-2", hypothesis_id="H_shared", subject_id=A, space_id=SHARED_2,
        support=0.2))

    in_s1 = store.hypotheses.list_for_subject(A, space_id=SHARED_1)
    in_s2 = store.hypotheses.list_for_subject(A, space_id=SHARED_2)
    assert [h.support.value for h in in_s1] == [0.9]
    assert [h.support.value for h in in_s2] == [0.2]
    # A hypothesis in SHARED_1 must not appear when querying SHARED_2.
    assert store.hypotheses.latest(HypothesisId("H_shared"), space_id=SHARED_1) is not None
    assert store.hypotheses.list_for_subject(A, space_id=PERSONAL) == []  # C: personal empty


def test_prediction_does_not_leak_across_subjects_or_spaces(store: Any) -> None:
    """F. predictions crossing boundaries (subject and space)."""
    store.predictions.add(make_prediction(
        prediction_id="p-a", hyps=("H_A",), subject_id=A))
    store.predictions.add(make_prediction(
        prediction_id="p-b", hyps=("H_B",), subject_id=B))
    store.predictions.add(make_prediction(
        prediction_id="p-shared", hyps=("H_A",), subject_id=A, space_id=SHARED_1))

    assert [p.id for p in store.predictions.list_for_subject(A)] == ["p-a"]
    assert [p.id for p in store.predictions.list_for_subject(B)] == ["p-b"]
    assert [p.id for p in store.predictions.list_for_subject(A, space_id=SHARED_1)] == ["p-shared"]
    # D. two unrelated shared spaces don't see each other.
    assert store.predictions.list_for_subject(A, space_id=SHARED_2) == []


def test_evidence_does_not_leak_across_spaces(store: Any) -> None:
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    from tests.conftest import make_evidence

    store.evidence.add(make_evidence(evidence_id="e1", subject_id=A, space_id=SHARED_1))
    store.evidence.add(make_evidence(evidence_id="e2", subject_id=A, space_id=SHARED_2))
    assert [e.id for e in store.evidence.list_for_subject(A, space_id=SHARED_1)] == ["e1"]
    assert [e.id for e in store.evidence.list_for_subject(A, space_id=SHARED_2)] == ["e2"]
    assert store.evidence.list_for_subject(A, space_id=PERSONAL) == []
    _ = now


def _world_model(subject: SubjectId, space: SpaceId, version: str) -> WorldModel:
    return WorldModel(
        model_version_id=WorldModelVersionId(version),
        subject_id=subject,
        reasoning_system_id=ReasoningSystemId("sys"),
        model_uncertainty=ModelUncertainty(0.5),
        active_hypothesis_ids=(HypothesisId("H_x"),),
        active_prediction_ids=(),
        active_inquiry_ids=(),
        created_at=T0,
        space_id=space,
    )


def test_world_model_does_not_leak_across_spaces(store: Any) -> None:
    """G. WorldModel assembly crossing boundaries — same subject, two spaces."""
    store.world_models.append_version(_world_model(A, SHARED_1, "wm-1"))
    store.world_models.set_current_pointer(CurrentModelSnapshot(
        subject_id=A, model_version_id=WorldModelVersionId("wm-1"),
        committed_at=T0, space_id=SHARED_1))

    assert store.world_models.get_current_model(A, space_id=SHARED_1) is not None
    # A different space sees nothing for the same subject.
    assert store.world_models.get_current_model(A, space_id=SHARED_2) is None
    assert store.world_models.get_version(A, WorldModelVersionId("wm-1"), space_id=SHARED_2) is None
    # And the same version id may exist independently in another space.
    store.world_models.append_version(_world_model(A, SHARED_2, "wm-1"))
    assert store.world_models.get_version(A, WorldModelVersionId("wm-1"), space_id=SHARED_2) is not None


def test_ledger_is_partitioned_by_space(store: Any) -> None:
    def event(space: SpaceId) -> RevisionEvent:
        return RevisionEvent(
            id=RevisionEventId("r"),
            subject_id=A,
            affected_object_id=ObjectRef("H_x"),
            outcome=RevisionOutcome.HYPOTHESIZE,
            triggering_evidence_ids=(EvidenceRecordId("e1"),),
            status=RevisionStatus.COMMITTED,
            created_at=T0,
            to_model_version_id=WorldModelVersionId("wm-1"),
            space_id=space,
        )

    store.ledger.append(event(SHARED_1))
    store.ledger.append(event(SHARED_1))
    store.ledger.append(event(SHARED_2))
    assert len(store.ledger.read(A, space_id=SHARED_1)) == 2
    assert len(store.ledger.read(A, space_id=SHARED_2)) == 1  # independent sequence
    assert store.ledger.read(A, space_id=PERSONAL) == []


# ===========================================================================
# End-to-end service isolation (A, B, C, D) through the reasoning engine
# ===========================================================================


class _ProposesPerSubject:
    """Proposes a hypothesis id ``H_<subject>`` per subject, then supports it."""

    def appraise(self, subject_id: SubjectId, evidence: Any, working: Any) -> Appraisal:
        hid = HypothesisId(f"H_{subject_id}")
        if any(w.hypothesis_id == hid for w in working):
            return Appraisal(supports=(hid,))
        return Appraisal(proposals=(ProposedHypothesis(hid, f"explanation for {subject_id}", 0.8, ()),))


def _service() -> ReasoningService:
    deps = build_in_memory_dependencies(
        appraiser=_ProposesPerSubject(),
        clock=ManualClock(),
        ids=SequentialIdGenerator(),
    )
    return ReasoningService(deps)


def _ev(subject: SubjectId, space: SpaceId | None = None) -> EvidenceInput:
    return EvidenceInput(
        subject_id=subject,
        evidence_class=EvidenceClass.BEHAVIOURAL,
        content="observation",
        source="reflection",
        reliability=0.8,
        classification_confidence=0.9,
        space_id=space,
    )


def test_two_subjects_same_space_are_isolated() -> None:
    """A + E + F + G end-to-end: A and B in the same space share nothing."""
    svc = _service()
    svc.record_interaction(A, [_ev(A)], space_id=SHARED_1)
    svc.record_interaction(B, [_ev(B)], space_id=SHARED_1)
    view = svc.view()

    a = view.understanding(A, space_id=SHARED_1)
    b = view.understanding(B, space_id=SHARED_1)
    assert {h.hypothesis_id for h in a.hypotheses} == {HypothesisId("H_subject-A")}
    assert {h.hypothesis_id for h in b.hypotheses} == {HypothesisId("H_subject-B")}
    # A's hypotheses/predictions never appear for B.
    assert all(h.subject_id == A for h in a.hypotheses)
    assert all(p.subject_id == B for p in b.predictions)
    # The WorldModel for B contains no hypothesis owned by A.
    assert HypothesisId("H_subject-A") not in {h.hypothesis_id for h in b.hypotheses}


def test_same_subject_two_spaces_are_isolated() -> None:
    """B: subject X reasons independently in SHARED_1 vs SHARED_2."""
    svc = _service()
    # Space 1 gets three reinforcing observations; space 2 gets one.
    for _ in range(3):
        svc.record_interaction(A, [_ev(A)], space_id=SHARED_1)
    svc.record_interaction(A, [_ev(A)], space_id=SHARED_2)
    view = svc.view()

    s1 = view.understanding(A, space_id=SHARED_1)
    s2 = view.understanding(A, space_id=SHARED_2)
    # Same subject + same hypothesis lineage id, but independent support/history.
    assert s1.revision_count > s2.revision_count
    assert s1.hypotheses[0].support.value > s2.hypotheses[0].support.value
    assert s1.hypotheses[0].space_id == SHARED_1
    assert s2.hypotheses[0].space_id == SHARED_2
    # Personal space has seen nothing.
    assert view.understanding(A, space_id=PERSONAL).hypotheses == ()


def test_personal_vs_shared_and_two_shared_spaces_isolated() -> None:
    """C + D: personal vs shared, and two unrelated shared spaces, are isolated."""
    svc = _service()
    svc.record_interaction(A, [_ev(A)], space_id=PERSONAL)
    svc.record_interaction(A, [_ev(A)], space_id=SHARED_1)
    svc.record_interaction(A, [_ev(A)], space_id=SHARED_2)
    view = svc.view()

    for space in (PERSONAL, SHARED_1, SHARED_2):
        u = view.understanding(A, space_id=space)
        assert len(u.hypotheses) == 1
        assert u.hypotheses[0].space_id == space
    # No cross-contamination: each space has exactly one revision.
    assert view.understanding(A, space_id=PERSONAL).revision_count == 1
    assert view.understanding(A, space_id=SHARED_1).revision_count == 1
    assert view.understanding(A, space_id=SHARED_2).revision_count == 1


# ===========================================================================
# Invalid evidence ownership is rejected
# ===========================================================================


def test_evidence_with_mismatched_subject_is_rejected() -> None:
    svc = _service()
    # The interaction is for subject A, but the evidence names subject B.
    with pytest.raises(InvariantViolation, match="ownership does not match"):
        svc.record_interaction(A, [_ev(B)], space_id=SHARED_1)


def test_evidence_with_mismatched_space_is_rejected() -> None:
    svc = _service()
    # The interaction is in SHARED_1, but the evidence declares SHARED_2.
    with pytest.raises(InvariantViolation, match="ownership does not match"):
        svc.record_interaction(A, [_ev(A, space=SHARED_2)], space_id=SHARED_1)


def test_reasoning_scope_rejects_empty_components() -> None:
    with pytest.raises(InvariantViolation):
        ReasoningScope(space_id=SpaceId(""), subject_id=A)
    with pytest.raises(InvariantViolation):
        ReasoningScope(space_id=SHARED_1, subject_id=SubjectId(""))
