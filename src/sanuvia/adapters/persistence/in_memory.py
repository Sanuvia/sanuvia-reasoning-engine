"""In-memory implementations of every repository port.

Intended for tests and the Phase 0 exit-test harness — no external process, no
durability. They honour the *contracts* of the ports precisely: immutable stores
never mutate what was written, the ledger assigns per-subject monotonic sequence
numbers and only accepts committed events, and re-evaluated hypotheses/inquiries
are retained as history rather than overwritten.

Each store is offered individually, and ``InMemoryReasoningStore`` bundles a
consistent set of them for convenient wiring.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

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
    InvariantViolation,
    ObjectRef,
    Prediction,
    PredictionId,
    ProvenanceRecord,
    ProvenanceRecordId,
    RecognitionEvent,
    RevisionEvent,
    RevisionLedgerEntry,
    RevisionStatus,
    SpaceId,
    SubjectId,
    SystemModellingContext,
    WorldModel,
    WorldModelVersionId,
)


class InMemoryEvidenceStore:
    """Implements ``EvidenceStore``."""

    def __init__(self) -> None:
        self._by_id: dict[EvidenceRecordId, EvidenceRecord] = {}

    def add(self, record: EvidenceRecord) -> None:
        if record.id in self._by_id:
            raise InvariantViolation(f"EvidenceRecord {record.id} already exists")
        self._by_id[record.id] = record

    def get(self, evidence_id: EvidenceRecordId) -> EvidenceRecord | None:
        return self._by_id.get(evidence_id)

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[EvidenceRecord]:
        return [
            e
            for e in self._by_id.values()
            if e.subject_id == subject_id and e.space_id == space_id
        ]


class InMemoryInferenceStore:
    """Implements ``InferenceStore`` — kept wholly separate from evidence."""

    def __init__(self) -> None:
        self._by_id: dict[InferenceRecordId, InferenceRecord] = {}

    def add(self, record: InferenceRecord) -> None:
        if record.id in self._by_id:
            raise InvariantViolation(f"InferenceRecord {record.id} already exists")
        self._by_id[record.id] = record

    def get(self, inference_id: InferenceRecordId) -> InferenceRecord | None:
        return self._by_id.get(inference_id)

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[InferenceRecord]:
        return [
            i
            for i in self._by_id.values()
            if i.subject_id == subject_id and i.space_id == space_id
        ]


class InMemoryHypothesisRepository:
    """Implements ``HypothesisRepository`` with lineage retention (FR-RS-003)."""

    def __init__(self) -> None:
        # Insertion-ordered list of all immutable evaluations.
        self._records: list[Hypothesis] = []

    def add(self, hypothesis: Hypothesis) -> None:
        self._records.append(hypothesis)

    def get_record(
        self, record_id: HypothesisRecordId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Hypothesis | None:
        for h in self._records:
            if h.record_id == record_id and h.space_id == space_id:
                return h
        return None

    def latest(
        self, hypothesis_id: HypothesisId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Hypothesis | None:
        latest: Hypothesis | None = None
        for h in self._records:
            if h.hypothesis_id == hypothesis_id and h.space_id == space_id:
                latest = h
        return latest

    def lineage(
        self, hypothesis_id: HypothesisId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Hypothesis]:
        return [
            h
            for h in self._records
            if h.hypothesis_id == hypothesis_id and h.space_id == space_id
        ]

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Hypothesis]:
        # Latest evaluation per lineage, preserving first-seen order. Isolation
        # (Finding 1): only lineages owned by THIS (space, subject) are considered
        # — a hypothesis for another subject or space is never returned.
        latest: dict[HypothesisId, Hypothesis] = {}
        order: list[HypothesisId] = []
        for h in self._records:
            if h.subject_id != subject_id or h.space_id != space_id:
                continue
            if h.hypothesis_id not in latest:
                order.append(h.hypothesis_id)
            latest[h.hypothesis_id] = h
        return [latest[hid] for hid in order]


class InMemoryPredictionRepository:
    """Implements ``PredictionRepository``."""

    def __init__(self) -> None:
        self._by_id: dict[PredictionId, Prediction] = {}
        self._order: list[PredictionId] = []

    def add(self, prediction: Prediction) -> None:
        if prediction.id not in self._by_id:
            self._order.append(prediction.id)
        self._by_id[prediction.id] = prediction

    def get(self, prediction_id: PredictionId) -> Prediction | None:
        return self._by_id.get(prediction_id)

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Prediction]:
        # Isolation (Finding 1): filter by BOTH subject and space.
        return [
            self._by_id[pid]
            for pid in self._order
            if self._by_id[pid].subject_id == subject_id
            and self._by_id[pid].space_id == space_id
        ]


class InMemoryInquiryRepository:
    """Implements ``InquiryRepository`` with status history retention."""

    def __init__(self) -> None:
        self._records: list[Inquiry] = []

    def add(self, inquiry: Inquiry) -> None:
        self._records.append(inquiry)

    def latest(self, inquiry_id: InquiryId) -> Inquiry | None:
        latest: Inquiry | None = None
        for inq in self._records:
            if inq.id == inquiry_id:
                latest = inq
        return latest

    def history(self, inquiry_id: InquiryId) -> Sequence[Inquiry]:
        return [inq for inq in self._records if inq.id == inquiry_id]

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Inquiry]:
        latest: dict[InquiryId, Inquiry] = {}
        order: list[InquiryId] = []
        for inq in self._records:
            if inq.subject_id != subject_id or inq.space_id != space_id:
                continue
            if inq.id not in latest:
                order.append(inq.id)
            latest[inq.id] = inq
        return [latest[iid] for iid in order]


class InMemoryWorldModelRepository:
    """Implements ``WorldModelRepository`` (append-only versions + pointer)."""

    def __init__(self) -> None:
        # Keyed by (space, subject, version) and (space, subject) so the same
        # subject id in two spaces has fully separate model history (Finding 1).
        self._versions: dict[
            tuple[SpaceId, SubjectId, WorldModelVersionId], WorldModel
        ] = {}
        self._current: dict[tuple[SpaceId, SubjectId], CurrentModelSnapshot] = {}

    def append_version(self, model: WorldModel) -> None:
        key = (model.space_id, model.subject_id, model.model_version_id)
        if key in self._versions:
            raise InvariantViolation(
                f"WorldModel version {model.model_version_id} already exists"
            )
        self._versions[key] = model

    def get_version(
        self,
        subject_id: SubjectId,
        version_id: WorldModelVersionId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> WorldModel | None:
        return self._versions.get((space_id, subject_id, version_id))

    def get_current_pointer(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> CurrentModelSnapshot | None:
        return self._current.get((space_id, subject_id))

    def set_current_pointer(self, pointer: CurrentModelSnapshot) -> None:
        self._current[(pointer.space_id, pointer.subject_id)] = pointer

    def get_current_model(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> WorldModel | None:
        pointer = self._current.get((space_id, subject_id))
        if pointer is None:
            return None
        return self._versions.get((space_id, subject_id, pointer.model_version_id))


class InMemoryRevisionLedgerStore:
    """Implements ``RevisionLedgerStore`` — append-only, monotonic per subject."""

    def __init__(self) -> None:
        # Per (space, subject) monotonic sequence — a subject in two spaces keeps
        # two independent ledgers (Finding 1).
        self._by_scope: dict[tuple[SpaceId, SubjectId], list[RevisionLedgerEntry]] = {}

    def append(self, event: RevisionEvent) -> RevisionLedgerEntry:
        if event.status is not RevisionStatus.COMMITTED:
            raise InvariantViolation(
                "Only committed RevisionEvents may be appended (FR-MR-003/005)"
            )
        entries = self._by_scope.setdefault((event.space_id, event.subject_id), [])
        entry = RevisionLedgerEntry(
            sequence_no=len(entries),
            revision_event=event,
            # Append time is taken as the event's creation time; a dedicated
            # append clock can be injected later without changing the contract.
            appended_at=event.created_at,
        )
        entries.append(entry)
        return entry

    def read(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[RevisionLedgerEntry]:
        return list(self._by_scope.get((space_id, subject_id), []))

    def read_since(
        self,
        subject_id: SubjectId,
        after_sequence_no: int,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Sequence[RevisionLedgerEntry]:
        return [
            e
            for e in self._by_scope.get((space_id, subject_id), [])
            if e.sequence_no > after_sequence_no
        ]


class InMemoryAnomalyResolutionStore:
    """Implements ``AnomalyResolutionStore``."""

    def __init__(self) -> None:
        self._by_id: dict[AnomalyResolutionId, AnomalyResolution] = {}

    def add(self, resolution: AnomalyResolution) -> None:
        self._by_id[resolution.id] = resolution

    def get(self, resolution_id: AnomalyResolutionId) -> AnomalyResolution | None:
        return self._by_id.get(resolution_id)


class InMemoryProvenanceRepository:
    """Implements ``ProvenanceRepository``."""

    def __init__(self) -> None:
        self._by_id: dict[ProvenanceRecordId, ProvenanceRecord] = {}

    def add(self, record: ProvenanceRecord) -> None:
        self._by_id[record.id] = record

    def get(self, record_id: ProvenanceRecordId) -> ProvenanceRecord | None:
        return self._by_id.get(record_id)


class InMemoryRecognitionRepository:
    """Implements ``RecognitionRepository``."""

    def __init__(self) -> None:
        self._events: list[RecognitionEvent] = []

    def add(self, event: RecognitionEvent) -> None:
        self._events.append(event)

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[RecognitionEvent]:
        return [
            e
            for e in self._events
            if e.subject_id == subject_id and e.space_id == space_id
        ]


class InMemoryDependencyGraphStore:
    """Implements ``DependencyGraphStore``."""

    def __init__(self) -> None:
        self._edges: list[DependencyEdge] = []

    def add_edge(self, edge: DependencyEdge) -> None:
        self._edges.append(edge)

    def edges_from(self, ref: ObjectRef) -> Sequence[DependencyEdge]:
        return [e for e in self._edges if e.from_ref == ref]

    def edges_to(self, ref: ObjectRef) -> Sequence[DependencyEdge]:
        return [e for e in self._edges if e.to_ref == ref]


class InMemorySystemModellingContextStore:
    """Implements ``SystemModellingContextStore``."""

    def __init__(self) -> None:
        self._by_subject: dict[SubjectId, SystemModellingContext] = {}

    def put(self, subject_id: SubjectId, context: SystemModellingContext) -> None:
        self._by_subject[subject_id] = context

    def get(self, subject_id: SubjectId) -> SystemModellingContext | None:
        return self._by_subject.get(subject_id)


@dataclass
class InMemoryReasoningStore:
    """A consistent bundle of in-memory stores for convenient wiring.

    Each attribute satisfies the correspondingly-named repository port; the
    application can be constructed against the ports and handed this bundle's
    fields, keeping the engine unaware it is talking to in-memory adapters.
    """

    evidence: InMemoryEvidenceStore = field(default_factory=InMemoryEvidenceStore)
    inference: InMemoryInferenceStore = field(default_factory=InMemoryInferenceStore)
    hypotheses: InMemoryHypothesisRepository = field(
        default_factory=InMemoryHypothesisRepository
    )
    predictions: InMemoryPredictionRepository = field(
        default_factory=InMemoryPredictionRepository
    )
    inquiries: InMemoryInquiryRepository = field(
        default_factory=InMemoryInquiryRepository
    )
    world_models: InMemoryWorldModelRepository = field(
        default_factory=InMemoryWorldModelRepository
    )
    ledger: InMemoryRevisionLedgerStore = field(
        default_factory=InMemoryRevisionLedgerStore
    )
    anomalies: InMemoryAnomalyResolutionStore = field(
        default_factory=InMemoryAnomalyResolutionStore
    )
    provenance: InMemoryProvenanceRepository = field(
        default_factory=InMemoryProvenanceRepository
    )
    recognition: InMemoryRecognitionRepository = field(
        default_factory=InMemoryRecognitionRepository
    )
    dependencies: InMemoryDependencyGraphStore = field(
        default_factory=InMemoryDependencyGraphStore
    )
    modelling_context: InMemorySystemModellingContextStore = field(
        default_factory=InMemorySystemModellingContextStore
    )
