"""Repository ports — the persistence seam.

Every persistence concern is expressed here as a ``Protocol``. The domain and the
rest of the application depend only on these interfaces, never on a database, an
ORM, or a cloud service. Any store — in-memory, SQLite, Postgres, or a
self-hosted engine — is a valid adapter as long as it satisfies these contracts.
Swapping deployment target is therefore an adapter change with **no** effect on
the reasoning engine.

Contract-level invariants encoded by these ports:

* Evidence and Inference have **separate** stores. There is no method anywhere
  that accepts an ``InferenceRecord`` as evidence — the never-re-ingest rule
  (FR-EM-005) is enforced by the shape of the interfaces, not by convention.
* Stores holding immutable objects (evidence, world-model versions, ledger
  entries) expose **append/get** only — no update, no delete. Correction happens
  through revision, not mutation.
* The ``RevisionLedgerStore`` is append-only and authoritative (FR-MR-005).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from sanuvia.domain import (
    DEFAULT_SPACE_ID,
    AnomalyResolution,
    AnomalyResolutionId,
    CurrentModelSnapshot,
    DependencyEdge,
    EvidenceRecord,
    EvidenceRecordId,
    Hypothesis,
    HypothesisId,
    HypothesisRecordId,
    InferenceRecord,
    InferenceRecordId,
    Inquiry,
    InquiryId,
    ObjectRef,
    Prediction,
    PredictionId,
    ProvenanceRecord,
    ProvenanceRecordId,
    RecognitionEvent,
    RevisionEvent,
    RevisionLedgerEntry,
    SpaceId,
    SubjectId,
    SystemModellingContext,
    WorldModel,
    WorldModelVersionId,
)

# Isolation note (Finding 1): every subject-scoped query below is partitioned by
# BOTH ``space_id`` and ``subject_id``. ``space_id`` defaults to the single
# default space so existing single-space callers are unaffected, but a store
# MUST NOT return an entity owned by a different space or a different subject.


@runtime_checkable
class EvidenceStore(Protocol):
    """Immutable store of accepted evidence (FR-EM-001). Append + read only.

    Accepts ``EvidenceRecord`` exclusively. There is intentionally no overload
    that accepts an ``InferenceRecord`` (FR-EM-005)."""

    def add(self, record: EvidenceRecord) -> None: ...
    def get(self, evidence_id: EvidenceRecordId) -> EvidenceRecord | None: ...
    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[EvidenceRecord]: ...


@runtime_checkable
class InferenceStore(Protocol):
    """Immutable store of system-derived inferences (FR-EM-005), kept entirely
    separate from the evidence store so an inference can never be persisted as
    evidence."""

    def add(self, record: InferenceRecord) -> None: ...
    def get(self, inference_id: InferenceRecordId) -> InferenceRecord | None: ...
    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[InferenceRecord]: ...


@runtime_checkable
class HypothesisRepository(Protocol):
    """Append-only store of immutable hypothesis evaluations (FR-RS-001/003).

    Re-evaluations are appended as new records sharing a ``hypothesis_id``
    lineage; prior values are retained, never overwritten."""

    def add(self, hypothesis: Hypothesis) -> None: ...
    def get_record(
        self, record_id: HypothesisRecordId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Hypothesis | None: ...
    def latest(
        self,
        hypothesis_id: HypothesisId,
        subject_id: SubjectId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Hypothesis | None:
        """The most recent evaluation in a hypothesis's lineage.

        Isolation (Finding 1): the lookup scope is
        ``(space_id, subject_id, hypothesis_id)``. Two subjects in the same space
        may reuse the same ``hypothesis_id``; this must never return the other
        subject's record."""
        ...

    def lineage(
        self,
        hypothesis_id: HypothesisId,
        subject_id: SubjectId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Sequence[Hypothesis]:
        """All evaluations for a hypothesis, oldest first (revision history).

        Isolation (Finding 1): scoped by ``(space_id, subject_id, hypothesis_id)``
        so a lineage never mixes two subjects' records."""
        ...

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Hypothesis]:
        """Latest evaluation per lineage owned by ``(space_id, subject_id)``.

        Isolation (Finding 1): filters by BOTH subject and space — a hypothesis
        owned by another subject or space is never returned."""
        ...


@runtime_checkable
class PredictionRepository(Protocol):
    """Store of immutable predictions (FR-RS-004)."""

    def add(self, prediction: Prediction) -> None: ...
    def get(self, prediction_id: PredictionId) -> Prediction | None: ...
    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Prediction]:
        """Predictions owned by ``(space_id, subject_id)`` — filtered by BOTH
        subject and space (Finding 1)."""
        ...


@runtime_checkable
class InquiryRepository(Protocol):
    """Append-only store of Inquiry records including status changes (FR-IQ-003).

    Each status change is a new immutable record for the same ``InquiryId``; the
    prior record is retained as history."""

    def add(self, inquiry: Inquiry) -> None: ...
    def latest(self, inquiry_id: InquiryId) -> Inquiry | None: ...
    def history(self, inquiry_id: InquiryId) -> Sequence[Inquiry]: ...
    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Inquiry]:
        """Latest record per Inquiry owned by ``(space_id, subject_id)``."""
        ...


@runtime_checkable
class WorldModelRepository(Protocol):
    """Append-only store of immutable WorldModel versions plus the current
    pointer (FR-PU-001/003).

    A revision appends a *new* version; the old version is never mutated. The
    ``CurrentModelSnapshot`` pointer identifies the latest committed version."""

    def append_version(self, model: WorldModel) -> None: ...
    def get_version(
        self,
        subject_id: SubjectId,
        version_id: WorldModelVersionId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> WorldModel | None: ...
    def get_current_pointer(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> CurrentModelSnapshot | None: ...
    def set_current_pointer(self, pointer: CurrentModelSnapshot) -> None: ...
    def get_current_model(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> WorldModel | None:
        """Resolve the current pointer to its WorldModel version, within the
        ``(space_id, subject_id)`` scope, if any."""
        ...


@runtime_checkable
class RevisionLedgerStore(Protocol):
    """Append-only, authoritative history of committed revisions (FR-MR-005).

    Appending assigns a per-subject monotonic ``sequence_no``. Entries are
    immutable and retrievable regardless of subsequent revisions. This ledger is
    shared infrastructure — it also backs the immutability guarantees of Evidence
    (FR-EM-003) and Persistent Understanding (FR-PU-003)."""

    def append(self, event: RevisionEvent) -> RevisionLedgerEntry:
        """Append a *committed* RevisionEvent and return its ledger entry."""
        ...

    def read(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[RevisionLedgerEntry]: ...
    def read_since(
        self,
        subject_id: SubjectId,
        after_sequence_no: int,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Sequence[RevisionLedgerEntry]:
        """Entries with ``sequence_no`` strictly greater than the argument —
        used to report 'revision events since the prior interaction'."""
        ...


@runtime_checkable
class AnomalyResolutionStore(Protocol):
    """Store of anomaly resolutions (FR-MR-004).

    OPEN (spec-unresolved): whether this is a distinct store or part of the
    RevisionLedger — especially for ``REJECT`` outcomes that yield no
    RevisionEvent — is not settled. Modelled as its own port so either wiring is
    possible without changing callers."""

    def add(self, resolution: AnomalyResolution) -> None: ...
    def get(self, resolution_id: AnomalyResolutionId) -> AnomalyResolution | None: ...


@runtime_checkable
class ProvenanceRepository(Protocol):
    """Store of WorldModel provenance records (FR-PU-004)."""

    def add(self, record: ProvenanceRecord) -> None: ...
    def get(self, record_id: ProvenanceRecordId) -> ProvenanceRecord | None: ...


@runtime_checkable
class RecognitionRepository(Protocol):
    """Store of RecognitionEvent records (FR-RF-001) — data only in Phase 0."""

    def add(self, event: RecognitionEvent) -> None: ...
    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[RecognitionEvent]: ...


@runtime_checkable
class DependencyGraphStore(Protocol):
    """Store of directed dependency/provenance edges between reasoning objects."""

    def add_edge(self, edge: DependencyEdge) -> None: ...
    def edges_from(self, ref: ObjectRef) -> Sequence[DependencyEdge]: ...
    def edges_to(self, ref: ObjectRef) -> Sequence[DependencyEdge]: ...


@runtime_checkable
class SystemModellingContextStore(Protocol):
    """Store for SystemModellingContext (FR-PU-005).

    OPEN (spec-unresolved): whether context is stored at all or supplied at
    retrieval time. Provided as a port so a stored-object adapter is possible;
    callers that treat context as a transient parameter simply do not use it."""

    def put(self, subject_id: SubjectId, context: SystemModellingContext) -> None: ...
    def get(self, subject_id: SubjectId) -> SystemModellingContext | None: ...
