"""SQLite implementations of every repository port.

A durable, single-file (or in-memory) alternative to the in-memory adapters,
satisfying exactly the same ports. It is pure infrastructure: it changes *where*
state lives, never *how* reasoning behaves. Decoded objects are rebuilt through
their normal constructors, so the same domain invariants apply.

Semantics are replicated from the in-memory adapters precisely (including that
``HypothesisRepository`` / ``PredictionRepository`` list across all subjects,
since those domain objects carry no subject field). Immutable stores expose
append/get only; the ledger is append-only with per-subject monotonic sequence
numbers.

Uses the Python standard library ``sqlite3`` only — no third-party dependency.
This module lives in the adapter layer; the architecture guard forbids such
imports in the domain/application core, not here.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from typing import Any, cast

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

from . import codec
from .sqlite_migration import SCHEMA_VERSION, migrate

# The v1 schema (Finding 1: space/subject isolation). Every subject-scoped table
# carries a ``space`` column, and hypotheses/predictions — which previously had
# no subject at all — now carry both ``space`` and ``subject`` so a query can
# never return an entity owned by another subject or space. WorldModel versions,
# the current pointer, and the ledger are keyed by (space, subject, ...).
_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (
    id TEXT PRIMARY KEY, space TEXT, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS inference (
    id TEXT PRIMARY KEY, space TEXT, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS hypotheses (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT, hypothesis_id TEXT, space TEXT, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS predictions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, space TEXT, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS inquiries (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, space TEXT, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS world_models (
    space TEXT, subject TEXT, version TEXT, json TEXT,
    PRIMARY KEY (space, subject, version));
CREATE TABLE IF NOT EXISTS current_pointer (
    space TEXT, subject TEXT, json TEXT, PRIMARY KEY (space, subject));
CREATE TABLE IF NOT EXISTS ledger (
    space TEXT, subject TEXT, seq INTEGER, json TEXT,
    PRIMARY KEY (space, subject, seq));
CREATE TABLE IF NOT EXISTS anomalies (id TEXT PRIMARY KEY, json TEXT);
CREATE TABLE IF NOT EXISTS provenance (id TEXT PRIMARY KEY, json TEXT);
CREATE TABLE IF NOT EXISTS recognition (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, space TEXT, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS dependencies (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, from_ref TEXT, to_ref TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS modelling_context (subject TEXT PRIMARY KEY, json TEXT);
"""

# The tables the ``reset()`` lifecycle operation clears (see SqliteReasoningStore).
_RESETTABLE_TABLES = (
    "evidence", "inference", "hypotheses", "predictions", "inquiries",
    "world_models", "current_pointer", "ledger", "anomalies", "provenance",
    "recognition", "dependencies", "modelling_context",
)


def _dump(obj: Any) -> str:
    return json.dumps(codec.encode(obj))


def _load(text: str) -> Any:
    return codec.decode(json.loads(text))


class _Base:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn


class SqliteEvidenceStore(_Base):
    def add(self, record: EvidenceRecord) -> None:
        try:
            self._conn.execute(
                "INSERT INTO evidence (id, space, subject, json) VALUES (?, ?, ?, ?)",
                (record.id, record.space_id, record.subject_id, _dump(record)),
            )
        except sqlite3.IntegrityError as exc:
            raise InvariantViolation(f"EvidenceRecord {record.id} already exists") from exc
        self._conn.commit()

    def get(self, evidence_id: EvidenceRecordId) -> EvidenceRecord | None:
        row = self._conn.execute(
            "SELECT json FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
        return None if row is None else cast(EvidenceRecord, _load(row[0]))

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[EvidenceRecord]:
        rows = self._conn.execute(
            "SELECT json FROM evidence WHERE subject = ? AND space = ? ORDER BY rowid",
            (subject_id, space_id),
        ).fetchall()
        return [cast(EvidenceRecord, _load(r[0])) for r in rows]


class SqliteInferenceStore(_Base):
    def add(self, record: InferenceRecord) -> None:
        try:
            self._conn.execute(
                "INSERT INTO inference (id, space, subject, json) VALUES (?, ?, ?, ?)",
                (record.id, record.space_id, record.subject_id, _dump(record)),
            )
        except sqlite3.IntegrityError as exc:
            raise InvariantViolation(f"InferenceRecord {record.id} already exists") from exc
        self._conn.commit()

    def get(self, inference_id: InferenceRecordId) -> InferenceRecord | None:
        row = self._conn.execute(
            "SELECT json FROM inference WHERE id = ?", (inference_id,)
        ).fetchone()
        return None if row is None else cast(InferenceRecord, _load(row[0]))

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[InferenceRecord]:
        rows = self._conn.execute(
            "SELECT json FROM inference WHERE subject = ? AND space = ? ORDER BY rowid",
            (subject_id, space_id),
        ).fetchall()
        return [cast(InferenceRecord, _load(r[0])) for r in rows]


class SqliteHypothesisRepository(_Base):
    def add(self, hypothesis: Hypothesis) -> None:
        self._conn.execute(
            "INSERT INTO hypotheses (record_id, hypothesis_id, space, subject, json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                hypothesis.record_id,
                hypothesis.hypothesis_id,
                hypothesis.space_id,
                hypothesis.subject_id,
                _dump(hypothesis),
            ),
        )
        self._conn.commit()

    def get_record(
        self, record_id: HypothesisRecordId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Hypothesis | None:
        row = self._conn.execute(
            "SELECT json FROM hypotheses WHERE record_id = ? AND space = ? "
            "ORDER BY seq DESC LIMIT 1",
            (record_id, space_id),
        ).fetchone()
        return None if row is None else cast(Hypothesis, _load(row[0]))

    def latest(
        self,
        hypothesis_id: HypothesisId,
        subject_id: SubjectId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Hypothesis | None:
        # Scope: (space_id, subject_id, hypothesis_id) — Finding 1.
        row = self._conn.execute(
            "SELECT json FROM hypotheses "
            "WHERE hypothesis_id = ? AND subject = ? AND space = ? "
            "ORDER BY seq DESC LIMIT 1",
            (hypothesis_id, subject_id, space_id),
        ).fetchone()
        return None if row is None else cast(Hypothesis, _load(row[0]))

    def lineage(
        self,
        hypothesis_id: HypothesisId,
        subject_id: SubjectId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Sequence[Hypothesis]:
        # Scope: (space_id, subject_id, hypothesis_id) — Finding 1.
        rows = self._conn.execute(
            "SELECT json FROM hypotheses "
            "WHERE hypothesis_id = ? AND subject = ? AND space = ? ORDER BY seq",
            (hypothesis_id, subject_id, space_id),
        ).fetchall()
        return [cast(Hypothesis, _load(r[0])) for r in rows]

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Hypothesis]:
        # Isolation (Finding 1): filter by BOTH subject and space in SQL, then
        # take the latest evaluation per lineage in first-seen order.
        rows = self._conn.execute(
            "SELECT hypothesis_id, json FROM hypotheses "
            "WHERE subject = ? AND space = ? ORDER BY seq",
            (subject_id, space_id),
        ).fetchall()
        latest: dict[str, Hypothesis] = {}
        order: list[str] = []
        for hid, blob in rows:
            if hid not in latest:
                order.append(hid)
            latest[hid] = cast(Hypothesis, _load(blob))
        return [latest[hid] for hid in order]


class SqlitePredictionRepository(_Base):
    def add(self, prediction: Prediction) -> None:
        self._conn.execute(
            "INSERT INTO predictions (id, space, subject, json) VALUES (?, ?, ?, ?)",
            (prediction.id, prediction.space_id, prediction.subject_id, _dump(prediction)),
        )
        self._conn.commit()

    def get(self, prediction_id: PredictionId) -> Prediction | None:
        row = self._conn.execute(
            "SELECT json FROM predictions WHERE id = ? ORDER BY seq DESC LIMIT 1",
            (prediction_id,),
        ).fetchone()
        return None if row is None else cast(Prediction, _load(row[0]))

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Prediction]:
        # Isolation (Finding 1): filter by BOTH subject and space.
        rows = self._conn.execute(
            "SELECT json FROM predictions WHERE subject = ? AND space = ? ORDER BY seq",
            (subject_id, space_id),
        ).fetchall()
        return [cast(Prediction, _load(r[0])) for r in rows]


class SqliteInquiryRepository(_Base):
    def add(self, inquiry: Inquiry) -> None:
        self._conn.execute(
            "INSERT INTO inquiries (id, space, subject, json) VALUES (?, ?, ?, ?)",
            (inquiry.id, inquiry.space_id, inquiry.subject_id, _dump(inquiry)),
        )
        self._conn.commit()

    def latest(self, inquiry_id: InquiryId) -> Inquiry | None:
        row = self._conn.execute(
            "SELECT json FROM inquiries WHERE id = ? ORDER BY seq DESC LIMIT 1",
            (inquiry_id,),
        ).fetchone()
        return None if row is None else cast(Inquiry, _load(row[0]))

    def history(self, inquiry_id: InquiryId) -> Sequence[Inquiry]:
        rows = self._conn.execute(
            "SELECT json FROM inquiries WHERE id = ? ORDER BY seq", (inquiry_id,)
        ).fetchall()
        return [cast(Inquiry, _load(r[0])) for r in rows]

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[Inquiry]:
        rows = self._conn.execute(
            "SELECT id, json FROM inquiries WHERE subject = ? AND space = ? ORDER BY seq",
            (subject_id, space_id),
        ).fetchall()
        latest: dict[str, Inquiry] = {}
        order: list[str] = []
        for iid, blob in rows:
            if iid not in latest:
                order.append(iid)
            latest[iid] = cast(Inquiry, _load(blob))
        return [latest[iid] for iid in order]


class SqliteWorldModelRepository(_Base):
    def append_version(self, model: WorldModel) -> None:
        try:
            self._conn.execute(
                "INSERT INTO world_models (space, subject, version, json) "
                "VALUES (?, ?, ?, ?)",
                (model.space_id, model.subject_id, model.model_version_id, _dump(model)),
            )
        except sqlite3.IntegrityError as exc:
            raise InvariantViolation(
                f"WorldModel version {model.model_version_id} already exists"
            ) from exc
        self._conn.commit()

    def get_version(
        self,
        subject_id: SubjectId,
        version_id: WorldModelVersionId,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> WorldModel | None:
        row = self._conn.execute(
            "SELECT json FROM world_models WHERE space = ? AND subject = ? AND version = ?",
            (space_id, subject_id, version_id),
        ).fetchone()
        return None if row is None else cast(WorldModel, _load(row[0]))

    def get_current_pointer(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> CurrentModelSnapshot | None:
        row = self._conn.execute(
            "SELECT json FROM current_pointer WHERE space = ? AND subject = ?",
            (space_id, subject_id),
        ).fetchone()
        return None if row is None else cast(CurrentModelSnapshot, _load(row[0]))

    def set_current_pointer(self, pointer: CurrentModelSnapshot) -> None:
        self._conn.execute(
            "INSERT INTO current_pointer (space, subject, json) VALUES (?, ?, ?) "
            "ON CONFLICT(space, subject) DO UPDATE SET json = excluded.json",
            (pointer.space_id, pointer.subject_id, _dump(pointer)),
        )
        self._conn.commit()

    def get_current_model(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> WorldModel | None:
        pointer = self.get_current_pointer(subject_id, space_id=space_id)
        if pointer is None:
            return None
        return self.get_version(subject_id, pointer.model_version_id, space_id=space_id)


class SqliteRevisionLedgerStore(_Base):
    def append(self, event: RevisionEvent) -> RevisionLedgerEntry:
        if event.status is not RevisionStatus.COMMITTED:
            raise InvariantViolation(
                "Only committed RevisionEvents may be appended (FR-MR-003/005)"
            )
        row = self._conn.execute(
            "SELECT COUNT(*) FROM ledger WHERE space = ? AND subject = ?",
            (event.space_id, event.subject_id),
        ).fetchone()
        seq = int(row[0])
        entry = RevisionLedgerEntry(
            sequence_no=seq, revision_event=event, appended_at=event.created_at
        )
        self._conn.execute(
            "INSERT INTO ledger (space, subject, seq, json) VALUES (?, ?, ?, ?)",
            (event.space_id, event.subject_id, seq, _dump(entry)),
        )
        self._conn.commit()
        return entry

    def read(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[RevisionLedgerEntry]:
        rows = self._conn.execute(
            "SELECT json FROM ledger WHERE space = ? AND subject = ? ORDER BY seq",
            (space_id, subject_id),
        ).fetchall()
        return [cast(RevisionLedgerEntry, _load(r[0])) for r in rows]

    def read_since(
        self,
        subject_id: SubjectId,
        after_sequence_no: int,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> Sequence[RevisionLedgerEntry]:
        rows = self._conn.execute(
            "SELECT json FROM ledger WHERE space = ? AND subject = ? AND seq > ? "
            "ORDER BY seq",
            (space_id, subject_id, after_sequence_no),
        ).fetchall()
        return [cast(RevisionLedgerEntry, _load(r[0])) for r in rows]


class SqliteAnomalyResolutionStore(_Base):
    def add(self, resolution: AnomalyResolution) -> None:
        self._conn.execute(
            "INSERT INTO anomalies (id, json) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET json = excluded.json",
            (resolution.id, _dump(resolution)),
        )
        self._conn.commit()

    def get(self, resolution_id: AnomalyResolutionId) -> AnomalyResolution | None:
        row = self._conn.execute(
            "SELECT json FROM anomalies WHERE id = ?", (resolution_id,)
        ).fetchone()
        return None if row is None else cast(AnomalyResolution, _load(row[0]))


class SqliteProvenanceRepository(_Base):
    def add(self, record: ProvenanceRecord) -> None:
        self._conn.execute(
            "INSERT INTO provenance (id, json) VALUES (?, ?) "
            "ON CONFLICT(id) DO UPDATE SET json = excluded.json",
            (record.id, _dump(record)),
        )
        self._conn.commit()

    def get(self, record_id: ProvenanceRecordId) -> ProvenanceRecord | None:
        row = self._conn.execute(
            "SELECT json FROM provenance WHERE id = ?", (record_id,)
        ).fetchone()
        return None if row is None else cast(ProvenanceRecord, _load(row[0]))


class SqliteRecognitionRepository(_Base):
    def add(self, event: RecognitionEvent) -> None:
        self._conn.execute(
            "INSERT INTO recognition (space, subject, json) VALUES (?, ?, ?)",
            (event.space_id, event.subject_id, _dump(event)),
        )
        self._conn.commit()

    def list_for_subject(
        self, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> Sequence[RecognitionEvent]:
        rows = self._conn.execute(
            "SELECT json FROM recognition WHERE subject = ? AND space = ? ORDER BY seq",
            (subject_id, space_id),
        ).fetchall()
        return [cast(RecognitionEvent, _load(r[0])) for r in rows]


class SqliteDependencyGraphStore(_Base):
    def add_edge(self, edge: DependencyEdge) -> None:
        self._conn.execute(
            "INSERT INTO dependencies (from_ref, to_ref, json) VALUES (?, ?, ?)",
            (edge.from_ref, edge.to_ref, _dump(edge)),
        )
        self._conn.commit()

    def edges_from(self, ref: ObjectRef) -> Sequence[DependencyEdge]:
        rows = self._conn.execute(
            "SELECT json FROM dependencies WHERE from_ref = ? ORDER BY seq", (ref,)
        ).fetchall()
        return [cast(DependencyEdge, _load(r[0])) for r in rows]

    def edges_to(self, ref: ObjectRef) -> Sequence[DependencyEdge]:
        rows = self._conn.execute(
            "SELECT json FROM dependencies WHERE to_ref = ? ORDER BY seq", (ref,)
        ).fetchall()
        return [cast(DependencyEdge, _load(r[0])) for r in rows]


class SqliteSystemModellingContextStore(_Base):
    def put(self, subject_id: SubjectId, context: SystemModellingContext) -> None:
        self._conn.execute(
            "INSERT INTO modelling_context (subject, json) VALUES (?, ?) "
            "ON CONFLICT(subject) DO UPDATE SET json = excluded.json",
            (subject_id, _dump(context)),
        )
        self._conn.commit()

    def get(self, subject_id: SubjectId) -> SystemModellingContext | None:
        row = self._conn.execute(
            "SELECT json FROM modelling_context WHERE subject = ?", (subject_id,)
        ).fetchone()
        return None if row is None else cast(SystemModellingContext, _load(row[0]))


class SqliteReasoningStore:
    """A consistent bundle of SQLite-backed stores over one connection.

    Mirrors ``InMemoryReasoningStore``'s attribute names so wiring can use either
    interchangeably. ``path`` defaults to an in-memory database; pass a file path
    for durability.
    """

    def __init__(self, path: str = ":memory:") -> None:
        # check_same_thread=False: under the threading HTTP adapter the store may
        # be constructed in one worker thread and read in another. Access is
        # externally serialised (the server guards every request with a single
        # lock), so sharing one connection across threads is safe. This is a
        # transport/threading concern only — it does not alter any reasoning
        # behaviour or the stored data.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        # Create/upgrade the schema. On a legacy (pre-space) database this
        # migrates existing rows in place, preserving data (see sqlite_migration).
        migrate(self._conn, _SCHEMA)
        self.evidence = SqliteEvidenceStore(self._conn)
        self.inference = SqliteInferenceStore(self._conn)
        self.hypotheses = SqliteHypothesisRepository(self._conn)
        self.predictions = SqlitePredictionRepository(self._conn)
        self.inquiries = SqliteInquiryRepository(self._conn)
        self.world_models = SqliteWorldModelRepository(self._conn)
        self.ledger = SqliteRevisionLedgerStore(self._conn)
        self.anomalies = SqliteAnomalyResolutionStore(self._conn)
        self.provenance = SqliteProvenanceRepository(self._conn)
        self.recognition = SqliteRecognitionRepository(self._conn)
        self.dependencies = SqliteDependencyGraphStore(self._conn)
        self.modelling_context = SqliteSystemModellingContextStore(self._conn)

    def reset(self) -> None:
        """Clear ALL reasoning state from this database (a *test-harness*
        lifecycle operation — Finding 2).

        The deterministic review harness reruns a Test Case by rebuilding a fresh
        engine with a deterministic id generator that restarts at ``evidence-1``.
        Against a durable SQLite file whose rows survive, that reissued id would
        collide. ``reset()`` truncates every table so a deterministic rerun is
        clean and reproduces byte-identically.

        This is emphatically NOT a production/durable operation: durable
        reasoning for real subjects is never reset (it uses collision-safe ids
        and only ever appends). See ``docs/reset-and-rerun.md``.
        """
        for table in _RESETTABLE_TABLES:
            self._conn.execute(f"DELETE FROM {table}")
        # Reset AUTOINCREMENT counters so a rerun is byte-identical, if present.
        if self._conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='sqlite_sequence'"
        ).fetchone():
            self._conn.execute("DELETE FROM sqlite_sequence")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
