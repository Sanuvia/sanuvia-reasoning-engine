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
    SubjectId,
    SystemModellingContext,
    WorldModel,
    WorldModelVersionId,
)

from . import codec

_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS inference (id TEXT PRIMARY KEY, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS hypotheses (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT, hypothesis_id TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS predictions (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS inquiries (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS world_models (
    subject TEXT, version TEXT, json TEXT, PRIMARY KEY (subject, version));
CREATE TABLE IF NOT EXISTS current_pointer (subject TEXT PRIMARY KEY, json TEXT);
CREATE TABLE IF NOT EXISTS ledger (
    subject TEXT, seq INTEGER, json TEXT, PRIMARY KEY (subject, seq));
CREATE TABLE IF NOT EXISTS anomalies (id TEXT PRIMARY KEY, json TEXT);
CREATE TABLE IF NOT EXISTS provenance (id TEXT PRIMARY KEY, json TEXT);
CREATE TABLE IF NOT EXISTS recognition (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS dependencies (
    seq INTEGER PRIMARY KEY AUTOINCREMENT, from_ref TEXT, to_ref TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS modelling_context (subject TEXT PRIMARY KEY, json TEXT);
"""


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
                "INSERT INTO evidence (id, subject, json) VALUES (?, ?, ?)",
                (record.id, record.subject_id, _dump(record)),
            )
        except sqlite3.IntegrityError as exc:
            raise InvariantViolation(f"EvidenceRecord {record.id} already exists") from exc
        self._conn.commit()

    def get(self, evidence_id: EvidenceRecordId) -> EvidenceRecord | None:
        row = self._conn.execute(
            "SELECT json FROM evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
        return None if row is None else cast(EvidenceRecord, _load(row[0]))

    def list_for_subject(self, subject_id: SubjectId) -> Sequence[EvidenceRecord]:
        rows = self._conn.execute(
            "SELECT json FROM evidence WHERE subject = ? ORDER BY rowid", (subject_id,)
        ).fetchall()
        return [cast(EvidenceRecord, _load(r[0])) for r in rows]


class SqliteInferenceStore(_Base):
    def add(self, record: InferenceRecord) -> None:
        try:
            self._conn.execute(
                "INSERT INTO inference (id, subject, json) VALUES (?, ?, ?)",
                (record.id, record.subject_id, _dump(record)),
            )
        except sqlite3.IntegrityError as exc:
            raise InvariantViolation(f"InferenceRecord {record.id} already exists") from exc
        self._conn.commit()

    def get(self, inference_id: InferenceRecordId) -> InferenceRecord | None:
        row = self._conn.execute(
            "SELECT json FROM inference WHERE id = ?", (inference_id,)
        ).fetchone()
        return None if row is None else cast(InferenceRecord, _load(row[0]))

    def list_for_subject(self, subject_id: SubjectId) -> Sequence[InferenceRecord]:
        rows = self._conn.execute(
            "SELECT json FROM inference WHERE subject = ? ORDER BY rowid", (subject_id,)
        ).fetchall()
        return [cast(InferenceRecord, _load(r[0])) for r in rows]


class SqliteHypothesisRepository(_Base):
    def add(self, hypothesis: Hypothesis) -> None:
        self._conn.execute(
            "INSERT INTO hypotheses (record_id, hypothesis_id, json) VALUES (?, ?, ?)",
            (hypothesis.record_id, hypothesis.hypothesis_id, _dump(hypothesis)),
        )
        self._conn.commit()

    def _all(self) -> list[Hypothesis]:
        rows = self._conn.execute(
            "SELECT json FROM hypotheses ORDER BY seq"
        ).fetchall()
        return [cast(Hypothesis, _load(r[0])) for r in rows]

    def get_record(self, record_id: HypothesisRecordId) -> Hypothesis | None:
        row = self._conn.execute(
            "SELECT json FROM hypotheses WHERE record_id = ? ORDER BY seq DESC LIMIT 1",
            (record_id,),
        ).fetchone()
        return None if row is None else cast(Hypothesis, _load(row[0]))

    def latest(self, hypothesis_id: HypothesisId) -> Hypothesis | None:
        row = self._conn.execute(
            "SELECT json FROM hypotheses WHERE hypothesis_id = ? ORDER BY seq DESC LIMIT 1",
            (hypothesis_id,),
        ).fetchone()
        return None if row is None else cast(Hypothesis, _load(row[0]))

    def lineage(self, hypothesis_id: HypothesisId) -> Sequence[Hypothesis]:
        rows = self._conn.execute(
            "SELECT json FROM hypotheses WHERE hypothesis_id = ? ORDER BY seq",
            (hypothesis_id,),
        ).fetchall()
        return [cast(Hypothesis, _load(r[0])) for r in rows]

    def list_for_subject(self, subject_id: SubjectId) -> Sequence[Hypothesis]:
        # Latest per lineage, first-seen order — identical to the in-memory
        # adapter (Hypothesis carries no subject; subject is not a filter here).
        latest: dict[HypothesisId, Hypothesis] = {}
        order: list[HypothesisId] = []
        for h in self._all():
            if h.hypothesis_id not in latest:
                order.append(h.hypothesis_id)
            latest[h.hypothesis_id] = h
        return [latest[hid] for hid in order]


class SqlitePredictionRepository(_Base):
    def add(self, prediction: Prediction) -> None:
        self._conn.execute(
            "INSERT INTO predictions (id, json) VALUES (?, ?)",
            (prediction.id, _dump(prediction)),
        )
        self._conn.commit()

    def get(self, prediction_id: PredictionId) -> Prediction | None:
        row = self._conn.execute(
            "SELECT json FROM predictions WHERE id = ? ORDER BY seq DESC LIMIT 1",
            (prediction_id,),
        ).fetchone()
        return None if row is None else cast(Prediction, _load(row[0]))

    def list_for_subject(self, subject_id: SubjectId) -> Sequence[Prediction]:
        rows = self._conn.execute(
            "SELECT json FROM predictions ORDER BY seq"
        ).fetchall()
        return [cast(Prediction, _load(r[0])) for r in rows]


class SqliteInquiryRepository(_Base):
    def add(self, inquiry: Inquiry) -> None:
        self._conn.execute(
            "INSERT INTO inquiries (id, subject, json) VALUES (?, ?, ?)",
            (inquiry.id, inquiry.subject_id, _dump(inquiry)),
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

    def list_for_subject(self, subject_id: SubjectId) -> Sequence[Inquiry]:
        rows = self._conn.execute(
            "SELECT id, json FROM inquiries WHERE subject = ? ORDER BY seq",
            (subject_id,),
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
                "INSERT INTO world_models (subject, version, json) VALUES (?, ?, ?)",
                (model.subject_id, model.model_version_id, _dump(model)),
            )
        except sqlite3.IntegrityError as exc:
            raise InvariantViolation(
                f"WorldModel version {model.model_version_id} already exists"
            ) from exc
        self._conn.commit()

    def get_version(
        self, subject_id: SubjectId, version_id: WorldModelVersionId
    ) -> WorldModel | None:
        row = self._conn.execute(
            "SELECT json FROM world_models WHERE subject = ? AND version = ?",
            (subject_id, version_id),
        ).fetchone()
        return None if row is None else cast(WorldModel, _load(row[0]))

    def get_current_pointer(
        self, subject_id: SubjectId
    ) -> CurrentModelSnapshot | None:
        row = self._conn.execute(
            "SELECT json FROM current_pointer WHERE subject = ?", (subject_id,)
        ).fetchone()
        return None if row is None else cast(CurrentModelSnapshot, _load(row[0]))

    def set_current_pointer(self, pointer: CurrentModelSnapshot) -> None:
        self._conn.execute(
            "INSERT INTO current_pointer (subject, json) VALUES (?, ?) "
            "ON CONFLICT(subject) DO UPDATE SET json = excluded.json",
            (pointer.subject_id, _dump(pointer)),
        )
        self._conn.commit()

    def get_current_model(self, subject_id: SubjectId) -> WorldModel | None:
        pointer = self.get_current_pointer(subject_id)
        if pointer is None:
            return None
        return self.get_version(subject_id, pointer.model_version_id)


class SqliteRevisionLedgerStore(_Base):
    def append(self, event: RevisionEvent) -> RevisionLedgerEntry:
        if event.status is not RevisionStatus.COMMITTED:
            raise InvariantViolation(
                "Only committed RevisionEvents may be appended (FR-MR-003/005)"
            )
        row = self._conn.execute(
            "SELECT COUNT(*) FROM ledger WHERE subject = ?", (event.subject_id,)
        ).fetchone()
        seq = int(row[0])
        entry = RevisionLedgerEntry(
            sequence_no=seq, revision_event=event, appended_at=event.created_at
        )
        self._conn.execute(
            "INSERT INTO ledger (subject, seq, json) VALUES (?, ?, ?)",
            (event.subject_id, seq, _dump(entry)),
        )
        self._conn.commit()
        return entry

    def read(self, subject_id: SubjectId) -> Sequence[RevisionLedgerEntry]:
        rows = self._conn.execute(
            "SELECT json FROM ledger WHERE subject = ? ORDER BY seq", (subject_id,)
        ).fetchall()
        return [cast(RevisionLedgerEntry, _load(r[0])) for r in rows]

    def read_since(
        self, subject_id: SubjectId, after_sequence_no: int
    ) -> Sequence[RevisionLedgerEntry]:
        rows = self._conn.execute(
            "SELECT json FROM ledger WHERE subject = ? AND seq > ? ORDER BY seq",
            (subject_id, after_sequence_no),
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
            "INSERT INTO recognition (subject, json) VALUES (?, ?)",
            (event.subject_id, _dump(event)),
        )
        self._conn.commit()

    def list_for_subject(self, subject_id: SubjectId) -> Sequence[RecognitionEvent]:
        rows = self._conn.execute(
            "SELECT json FROM recognition WHERE subject = ? ORDER BY seq",
            (subject_id,),
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
        self._conn = sqlite3.connect(path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
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

    def close(self) -> None:
        self._conn.close()
