"""Model Revision invariants (FR-MR-001 .. FR-MR-005) — the centerpiece."""

from __future__ import annotations

from datetime import timedelta

import pytest

from sanuvia.domain import (
    AnomalyDisposition,
    AnomalyResolution,
    AnomalyResolutionId,
    EvidenceRecordId,
    InvariantViolation,
    ModelRevisionResult,
    ObjectRef,
    RevisionEvent,
    RevisionEventId,
    RevisionLedgerEntry,
    RevisionOutcome,
    RevisionStatus,
    WorldModelVersionId,
)
from tests.conftest import SUBJECT, T0


def _proposed(event_id: str = "rev-1") -> RevisionEvent:
    return RevisionEvent(
        id=RevisionEventId(event_id),
        subject_id=SUBJECT,
        affected_object_id=ObjectRef("hyp-1"),
        outcome=RevisionOutcome.STRENGTHEN,
        triggering_evidence_ids=(EvidenceRecordId("ev-1"),),
        status=RevisionStatus.PROPOSED,
        created_at=T0,
    )


def test_revision_event_requires_triggering_evidence() -> None:
    # Every model revision must be traceable to evidence (FR-MR-001).
    with pytest.raises(InvariantViolation):
        RevisionEvent(
            id=RevisionEventId("rev-x"),
            subject_id=SUBJECT,
            affected_object_id=ObjectRef("hyp-1"),
            outcome=RevisionOutcome.STRENGTHEN,
            triggering_evidence_ids=(),
            status=RevisionStatus.PROPOSED,
            created_at=T0,
        )


def test_committed_event_must_record_target_version() -> None:
    with pytest.raises(InvariantViolation):
        RevisionEvent(
            id=RevisionEventId("rev-x"),
            subject_id=SUBJECT,
            affected_object_id=ObjectRef("hyp-1"),
            outcome=RevisionOutcome.STRENGTHEN,
            triggering_evidence_ids=(EvidenceRecordId("ev-1"),),
            status=RevisionStatus.COMMITTED,
            created_at=T0,
            to_model_version_id=None,
        )


def test_commit_transition_produces_committed_counterpart() -> None:
    proposed = _proposed()
    committed = proposed.committed(WorldModelVersionId("wm-2"))
    assert committed.status is RevisionStatus.COMMITTED
    assert committed.to_model_version_id == WorldModelVersionId("wm-2")
    # The original proposed event is unchanged (immutability).
    assert proposed.status is RevisionStatus.PROPOSED


def test_cannot_commit_twice() -> None:
    committed = _proposed().committed(WorldModelVersionId("wm-2"))
    with pytest.raises(InvariantViolation):
        committed.committed(WorldModelVersionId("wm-3"))


def test_ledger_entry_rejects_uncommitted_event() -> None:
    # Only committed RevisionEvents may be appended to the ledger
    # (FR-MR-003/005).
    with pytest.raises(InvariantViolation):
        RevisionLedgerEntry(sequence_no=0, revision_event=_proposed(), appended_at=T0)


def test_ledger_entry_accepts_committed_event() -> None:
    committed = _proposed().committed(WorldModelVersionId("wm-2"))
    entry = RevisionLedgerEntry(
        sequence_no=0, revision_event=committed, appended_at=T0 + timedelta(seconds=1)
    )
    assert entry.sequence_no == 0


def test_model_revision_result_supports_multiple_events() -> None:
    # FR-MR-001: a single interaction may fan out into multiple RevisionEvents.
    e1 = _proposed("rev-1").committed(WorldModelVersionId("wm-2"))
    e2 = _proposed("rev-2")  # left proposed
    result = ModelRevisionResult(
        subject_id=SUBJECT,
        revision_events=(e1, e2),
        new_model_version_id=WorldModelVersionId("wm-2"),
    )
    assert len(result.revision_events) == 2
    assert result.committed_events == (e1,)


def test_anomaly_resolution_requires_triggering_evidence() -> None:
    with pytest.raises(InvariantViolation):
        AnomalyResolution(
            id=AnomalyResolutionId("an-1"),
            subject_id=SUBJECT,
            disposition=AnomalyDisposition.REVISE,
            triggering_evidence_ids=(),
            created_at=T0,
        )


def test_all_five_dispositions_present_including_escalate() -> None:
    assert {d.name for d in AnomalyDisposition} == {
        "REJECT",
        "ASSIMILATE",
        "REVISE",
        "EXPAND",
        "ESCALATE",
    }
