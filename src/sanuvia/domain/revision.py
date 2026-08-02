"""Model Revision (FR-MR-001 .. FR-MR-005) — the centerpiece.

Understanding improves only when the current model is *revised* in response to
meaningful evidence. Everything else (evidence, hypotheses, uncertainty, inquiry)
exists to feed this. Reasoning is complete only when understanding has changed.

Flow (see Runtime Artefact 1):

  1. New evidence is assessed against existing understanding.
  2. If it contradicts, an ``AnomalyResolution`` is created carrying an
     ``AnomalyDisposition`` — decided **before** any RevisionEvent (FR-MR-004).
  3. One interaction may fan out into **multiple** ``RevisionEvent``s
     (FR-MR-001), each ``proposed`` then, if committed, ``committed``.
  4. Only a *committed* RevisionEvent is reflected in persistent understanding
     (FR-MR-003).
  5. Committed events are appended to the append-only ``RevisionLedger``
     (FR-MR-005), the authoritative history.

Deliberately NOT implemented in Phase 0 (represented as data only, never faked):

* The ``proposed -> committed`` transition *governance* is unspecified by the
  frozen spec. This module models both states; what *decides* the transition is
  left to an application-layer policy port in a later increment, not baked in.
* The ``ESCALATE`` disposition (second-order revision) is represented as a value
  but its escalation logic is deferred.
* Where an ``AnomalyResolution`` is persisted (its own store vs. the ledger),
  especially for ``REJECT`` outcomes that produce no RevisionEvent, is an open
  question — modelled as a distinct object so either choice remains available.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .errors import InvariantViolation
from .identifiers import (
    AnomalyResolutionId,
    EvidenceRecordId,
    ObjectRef,
    RevisionEventId,
    SubjectId,
    WorldModelVersionId,
)


class AnomalyDisposition(Enum):
    """How a contradiction against existing understanding is disposed of
    (FR-MR-004), decided before any RevisionEvent.

    ``ESCALATE`` denotes second-order model revision — its governing computation
    is deferred (interface-only). The other dispositions may proceed to
    RevisionEvent creation, except ``REJECT`` which produces none.
    """

    REJECT = "reject"
    ASSIMILATE = "assimilate"
    REVISE = "revise"
    EXPAND = "expand"
    ESCALATE = "escalate"


class RevisionOutcome(Enum):
    """The effect a committed revision has on the affected object (FR-MR-002).

    Note the distinction between ``WEAKEN`` and ``CONTRADICT`` lives here, at the
    RevisionEvent level — not as a hypothesis-level property.
    """

    STRENGTHEN = "strengthen"
    WEAKEN = "weaken"
    CONTRADICT = "contradict"
    HYPOTHESIZE = "hypothesize"


class RevisionStatus(Enum):
    """A RevisionEvent is ``PROPOSED`` and, if it commits, ``COMMITTED``
    (FR-MR-003). Only committed events are reflected in persistent
    understanding."""

    PROPOSED = "proposed"
    COMMITTED = "committed"


@dataclass(frozen=True, slots=True)
class AnomalyResolution:
    """The disposition of a contradiction, decided before any RevisionEvent
    (FR-MR-004)."""

    id: AnomalyResolutionId
    subject_id: SubjectId
    disposition: AnomalyDisposition
    triggering_evidence_ids: tuple[EvidenceRecordId, ...]
    created_at: datetime
    note: str = ""

    def __post_init__(self) -> None:
        if not self.triggering_evidence_ids:
            raise InvariantViolation(
                "An AnomalyResolution must cite the evidence that triggered the "
                "contradiction (FR-MR-004)"
            )


@dataclass(frozen=True, slots=True)
class RevisionEvent:
    """A single, immutable revision of the model (FR-MR-001/002/003).

    A ``PROPOSED`` event has no ``to_model_version_id`` yet; committing produces a
    new immutable event (via :meth:`committed`) carrying the ``to`` version. The
    ``from`` version is ``None`` for the very first revision of a subject's model.
    """

    id: RevisionEventId
    subject_id: SubjectId
    affected_object_id: ObjectRef
    outcome: RevisionOutcome
    triggering_evidence_ids: tuple[EvidenceRecordId, ...]
    status: RevisionStatus
    created_at: datetime
    from_model_version_id: WorldModelVersionId | None = None
    to_model_version_id: WorldModelVersionId | None = None
    anomaly_resolution_id: AnomalyResolutionId | None = None

    def __post_init__(self) -> None:
        if not self.triggering_evidence_ids:
            raise InvariantViolation(
                "A RevisionEvent must be traceable to one or more evidence "
                "records (FR-MR-001)"
            )
        if self.status is RevisionStatus.COMMITTED and self.to_model_version_id is None:
            raise InvariantViolation(
                "A committed RevisionEvent must record the model version it "
                "produced (FR-MR-003)"
            )

    def committed(self, to_model_version_id: WorldModelVersionId) -> "RevisionEvent":
        """Return the committed counterpart of a proposed event.

        This is a pure state-carrying transformation only — it does **not**
        decide *whether* the event should commit. That governance is unspecified
        by the frozen spec and belongs to an application policy, not here.
        """
        if self.status is RevisionStatus.COMMITTED:
            raise InvariantViolation("RevisionEvent is already committed")
        return RevisionEvent(
            id=self.id,
            subject_id=self.subject_id,
            affected_object_id=self.affected_object_id,
            outcome=self.outcome,
            triggering_evidence_ids=self.triggering_evidence_ids,
            status=RevisionStatus.COMMITTED,
            created_at=self.created_at,
            from_model_version_id=self.from_model_version_id,
            to_model_version_id=to_model_version_id,
            anomaly_resolution_id=self.anomaly_resolution_id,
        )


@dataclass(frozen=True, slots=True)
class ModelRevisionResult:
    """The result of one turn of the Core Loop's ``revise_model`` step.

    Must support **multiple** RevisionEvents per call — a single interaction may
    fan out into several revisions in different directions (FR-MR-001). May also
    carry the anomaly resolutions decided during processing and the new model
    version, if one was committed.
    """

    subject_id: SubjectId
    revision_events: tuple[RevisionEvent, ...]
    anomaly_resolutions: tuple[AnomalyResolution, ...] = ()
    new_model_version_id: WorldModelVersionId | None = None

    @property
    def committed_events(self) -> tuple[RevisionEvent, ...]:
        return tuple(
            e for e in self.revision_events if e.status is RevisionStatus.COMMITTED
        )


@dataclass(frozen=True, slots=True)
class RevisionLedgerEntry:
    """One append-only, immutable entry in the RevisionLedger (FR-MR-005).

    The ledger is the authoritative history of *committed* model changes and is
    shared infrastructure: it also backs the immutability promises of Evidence
    (FR-EM-003) and Persistent Understanding (FR-PU-003). ``sequence_no`` is a
    per-subject monotonically increasing position assigned on append.
    """

    sequence_no: int
    revision_event: RevisionEvent
    appended_at: datetime

    def __post_init__(self) -> None:
        if self.sequence_no < 0:
            raise InvariantViolation("RevisionLedgerEntry.sequence_no must be >= 0")
        if self.revision_event.status is not RevisionStatus.COMMITTED:
            raise InvariantViolation(
                "Only committed RevisionEvents may be appended to the "
                "RevisionLedger (FR-MR-003/005)"
            )
