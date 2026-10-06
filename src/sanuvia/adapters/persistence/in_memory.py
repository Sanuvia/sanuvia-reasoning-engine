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
    HypothesisLineage,
    IdentityAdjudication,
    IdentityAdjudicationId,
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
    SourceObservationRef,
    SpaceId,
    StatementVersion,
    SubjectId,
    SystemModellingContext,
    WorldModel,
    WorldModelVersionId,
)


class InMemoryEvidenceStore:
    """Implements ``EvidenceStore``, with the TD-03 source-reference index.

    The index is the ``SourceRefIndex`` §2 A requires: it "gives both
    directions", so a canonical ``evidence-N`` resolves to its
    ``(transcript, interaction, k)`` source observation and back. The
    within-interaction index ``k`` is what makes one interaction's three
    observations distinguishable -- the gap §2 A records.
    """

    def __init__(self) -> None:
        self._by_id: dict[EvidenceRecordId, EvidenceRecord] = {}
        #: source observation -> canonical evidence id (the forward direction).
        self._by_ref: dict[SourceObservationRef, EvidenceRecordId] = {}

    def add(self, record: EvidenceRecord) -> None:
        if record.id in self._by_id:
            raise InvariantViolation(f"EvidenceRecord {record.id} already exists")
        self._by_id[record.id] = record
        if record.source_ref is not None:
            self._by_ref[record.source_ref] = record.id

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

    # -- TD-03 source-reference mapping, both directions --------------------

    def id_for_ref(self, ref: SourceObservationRef) -> EvidenceRecordId | None:
        """Source observation -> canonical evidence id."""
        return self._by_ref.get(ref)

    def ref_for_id(self, evidence_id: EvidenceRecordId) -> SourceObservationRef | None:
        """Canonical evidence id -> source observation."""
        record = self._by_id.get(evidence_id)
        return None if record is None else record.source_ref

    def source_ref_index(self) -> dict[SourceObservationRef, EvidenceRecordId]:
        """The forward index, as complete-plan check 7 consumes it."""
        return dict(self._by_ref)

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct. The ref index is a second mutable
    # container owned by this store, so it is copied too -- a rejected plan
    # that left it populated would make check 7 reject the retry.
    def snapshot(self) -> object:
        return (dict(self._by_id), dict(self._by_ref))

    def restore(self, token: object) -> None:
        by_id, by_ref = token  # type: ignore[misc]
        self._by_id = dict(by_id)
        self._by_ref = dict(by_ref)


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

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        return dict(self._by_id)

    def restore(self, token: object) -> None:
        self._by_id = dict(token)  # type: ignore[index,arg-type]

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
        self,
        hypothesis_id: HypothesisId,
        subject_id: SubjectId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Hypothesis | None:
        # Scope: (space_id, subject_id, hypothesis_id) — Finding 1.
        latest: Hypothesis | None = None
        for h in self._records:
            if (
                h.hypothesis_id == hypothesis_id
                and h.subject_id == subject_id
                and h.space_id == space_id
            ):
                latest = h
        return latest

    def lineage(
        self,
        hypothesis_id: HypothesisId,
        subject_id: SubjectId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Sequence[Hypothesis]:
        # Scope: (space_id, subject_id, hypothesis_id) — Finding 1.
        return [
            h
            for h in self._records
            if h.hypothesis_id == hypothesis_id
            and h.subject_id == subject_id
            and h.space_id == space_id
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

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        return list(self._records)

    def restore(self, token: object) -> None:
        self._records = list(token)  # type: ignore[index,arg-type]

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

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        # Two containers: copying only ``_by_id`` would leave ``_order`` unrestored.
        return (dict(self._by_id), list(self._order))

    def restore(self, token: object) -> None:
        self._by_id, self._order = dict(token[0]), list(token[1])  # type: ignore[index,arg-type]

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

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        return list(self._records)

    def restore(self, token: object) -> None:
        self._records = list(token)  # type: ignore[index,arg-type]

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

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        # Two containers; both are restored together.
        return (dict(self._versions), dict(self._current))

    def restore(self, token: object) -> None:
        self._versions, self._current = dict(token[0]), dict(token[1])  # type: ignore[index,arg-type]

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

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        # NOTE: ``_by_scope`` is a dict **of lists**, and ``append`` mutates an
        # inner list in place. A shallow ``dict(...)`` would share those lists and
        # silently fail to roll back appended ledger entries, so each inner list is
        # copied too (Technical Design v1.5.4 §5.3).
        return {k: list(v) for k, v in self._by_scope.items()}

    def restore(self, token: object) -> None:
        self._by_scope = {k: list(v) for k, v in token.items()}  # type: ignore[index,arg-type]

class InMemoryAnomalyResolutionStore:
    """Implements ``AnomalyResolutionStore``."""

    def __init__(self) -> None:
        self._by_id: dict[AnomalyResolutionId, AnomalyResolution] = {}

    def add(self, resolution: AnomalyResolution) -> None:
        self._by_id[resolution.id] = resolution

    def get(self, resolution_id: AnomalyResolutionId) -> AnomalyResolution | None:
        return self._by_id.get(resolution_id)

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        return dict(self._by_id)

    def restore(self, token: object) -> None:
        self._by_id = dict(token)  # type: ignore[index,arg-type]

class InMemoryProvenanceRepository:
    """Implements ``ProvenanceRepository``."""

    def __init__(self) -> None:
        self._by_id: dict[ProvenanceRecordId, ProvenanceRecord] = {}

    def add(self, record: ProvenanceRecord) -> None:
        self._by_id[record.id] = record

    def get(self, record_id: ProvenanceRecordId) -> ProvenanceRecord | None:
        return self._by_id.get(record_id)

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        return dict(self._by_id)

    def restore(self, token: object) -> None:
        self._by_id = dict(token)  # type: ignore[index,arg-type]

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

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        return list(self._events)

    def restore(self, token: object) -> None:
        self._events = list(token)  # type: ignore[index,arg-type]

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

    def all_edges(self) -> Sequence[DependencyEdge]:
        """Every recorded edge. Used to exclude already-paired divergence
        candidates before disclosure (§2 J.1 rule 6b)."""
        return list(self._edges)

    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        return list(self._edges)

    def restore(self, token: object) -> None:
        self._edges = list(token)  # type: ignore[index,arg-type]

class InMemorySystemModellingContextStore:
    """Implements ``SystemModellingContextStore``."""

    def __init__(self) -> None:
        self._by_subject: dict[SubjectId, SystemModellingContext] = {}

    def put(self, subject_id: SubjectId, context: SystemModellingContext) -> None:
        self._by_subject[subject_id] = context

    def get(self, subject_id: SubjectId) -> SystemModellingContext | None:
        return self._by_subject.get(subject_id)



    # -- snapshot/restore (Technical Design v1.5.4 §5.3, F-9) --------------
    #
    # Each store copies **every mutable container it owns**, to whatever depth
    # its own shape requires. Record immutability is why these copies stay
    # cheap; it is NOT why they are correct.
    def snapshot(self) -> object:
        return dict(self._by_subject)

    def restore(self, token: object) -> None:
        self._by_subject = dict(token)  # type: ignore[index,arg-type]



class InMemoryHypothesisLineageStore:
    """Implements ``HypothesisLineageStore`` (Technical Design v1.5.4 §2 H, F-9).

    Holds the immutable half of a commitment signature, written once when
    ``DISTINCT_NEW`` is adjudicated. Indexed by the lineage key so retrieval can
    be bounded on ``(subject, attribution)`` only (F-2).
    """

    def __init__(self) -> None:
        self._by_id: dict[HypothesisId, HypothesisLineage] = {}
        #: M-2: a retrieval bound admits MANY lineages, so the index holds a
        #: list per key. ``attribution`` is a voice label (§2 H), so every
        #: commitment one voice holds about one subject shares its bound; a
        #: one-id-per-key index silently dropped all but the last.
        self._by_key: dict[
            tuple[SpaceId, SubjectId, str, str], list[HypothesisId]
        ] = {}

    def add(self, lineage: HypothesisLineage) -> None:
        if lineage.hypothesis_id in self._by_id:
            raise InvariantViolation(
                f"HypothesisLineage {lineage.hypothesis_id} already exists"
            )
        self._by_id[lineage.hypothesis_id] = lineage
        key = (
            lineage.space_id,
            lineage.subject_id,
            str(lineage.signature_subject),
            lineage.attribution,
        )
        # Appended in insertion order, never assigned: an earlier lineage under
        # the same bound must remain retrievable (M-2).
        self._by_key.setdefault(key, []).append(lineage.hypothesis_id)

    def get(self, hypothesis_id: HypothesisId) -> HypothesisLineage | None:
        return self._by_id.get(hypothesis_id)

    def find_by_key(
        self,
        subject_id: SubjectId,
        signature_subject: str,
        attribution: str,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> tuple[HypothesisId, ...]:
        """Every lineage the bound admits, in insertion order (F-2, M-2).

        ``claim_class`` is deliberately absent from this key: bounding retrieval
        on a versioned field would mean a candidate proposing a legitimate
        refinement failed to retrieve its own lineage.

        Returns a **tuple**, not a single id: the bound is
        ``(subject, attribution)`` where ``attribution`` is a voice label, so
        several distinct commitments legitimately share it once something with
        the authority to decide has said they are distinct.
        """
        return tuple(
            self._by_key.get((space_id, subject_id, signature_subject, attribution), ())
        )

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[HypothesisLineage]:
        return [
            lin
            for lin in self._by_id.values()
            if lin.subject_id == subject_id and lin.space_id == space_id
        ]

    # -- snapshot/restore (§5.3, F-9) ---------------------------------------
    # Two containers; both are restored together.
    def snapshot(self) -> object:
        # The key index now holds lists, so the inner lists are copied too --
        # a shallow dict copy would share them with the live store and a
        # rollback would leave an appended id behind (F-9).
        return (
            dict(self._by_id),
            {key: list(ids) for key, ids in self._by_key.items()},
        )

    def restore(self, token: object) -> None:
        by_id, by_key = token  # type: ignore[misc]
        self._by_id = dict(by_id)
        self._by_key = {key: list(ids) for key, ids in by_key.items()}


class InMemoryStatementVersionStore:
    """Implements ``StatementVersionStore`` (§2 I).

    Append-only. ``REFINE_EXISTING`` appends a version and never overwrites the
    prior statement; the current statement is a pointer to the latest accepted
    version. Statement **history** is retained because exact-match adjudication
    compares against every version of a lineage, not only the current one (F-2).
    """

    def __init__(self) -> None:
        self._by_lineage: dict[HypothesisId, list[StatementVersion]] = {}

    def append(self, version: StatementVersion) -> None:
        self._by_lineage.setdefault(version.hypothesis_id, []).append(version)

    def history(self, hypothesis_id: HypothesisId) -> Sequence[StatementVersion]:
        """Every accepted version, oldest first. Prior versions are never
        overwritten."""
        return list(self._by_lineage.get(hypothesis_id, []))

    def current(self, hypothesis_id: HypothesisId) -> StatementVersion | None:
        versions = self._by_lineage.get(hypothesis_id)
        return versions[-1] if versions else None

    # -- snapshot/restore (§5.3, F-9) ---------------------------------------
    # NOTE: dict **of lists**, and ``append`` mutates an inner list in place. A
    # shallow ``dict(...)`` would share those lists and silently fail to roll
    # back appended versions, so each inner list is copied too.
    def snapshot(self) -> object:
        return {k: list(v) for k, v in self._by_lineage.items()}

    def restore(self, token: object) -> None:
        self._by_lineage = {k: list(v) for k, v in token.items()}  # type: ignore[union-attr]


class InMemoryIdentityAdjudicationStore:
    """Implements ``IdentityAdjudicationStore`` (§2 D).

    A parked record creates and revises no hypothesis. Ruling Q2: Run 003
    creates, preserves and reports these and implements no resolution path.
    """

    def __init__(self) -> None:
        self._by_id: dict[IdentityAdjudicationId, IdentityAdjudication] = {}

    def add(self, record: IdentityAdjudication) -> None:
        if record.id in self._by_id:
            raise InvariantViolation(
                f"IdentityAdjudication {record.id} already exists"
            )
        self._by_id[record.id] = record

    def get(self, record_id: IdentityAdjudicationId) -> IdentityAdjudication | None:
        return self._by_id.get(record_id)

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[IdentityAdjudication]:
        return [
            r
            for r in self._by_id.values()
            if r.subject_id == subject_id and r.space_id == space_id
        ]

    # -- snapshot/restore (§5.3, F-9) ---------------------------------------
    def snapshot(self) -> object:
        return dict(self._by_id)

    def restore(self, token: object) -> None:
        self._by_id = dict(token)  # type: ignore[arg-type]


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
    # Semantic-state stores (Technical Design v1.5.4 §5.1, F-9, N-1). They are
    # fields of the bundle, so UnitOfWork covers them automatically and TD-17b's
    # parametrisation grows with the bundle rather than a fixed count.
    lineages: InMemoryHypothesisLineageStore = field(
        default_factory=InMemoryHypothesisLineageStore
    )
    statement_versions: InMemoryStatementVersionStore = field(
        default_factory=InMemoryStatementVersionStore
    )
    identity_adjudications: InMemoryIdentityAdjudicationStore = field(
        default_factory=InMemoryIdentityAdjudicationStore
    )
