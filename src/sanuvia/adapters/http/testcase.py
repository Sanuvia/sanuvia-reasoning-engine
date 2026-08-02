"""TestCase — one deterministic reasoning experiment for the review harness.

A Test Case holds an *ordered sequence of canonical EvidenceRecord specs* the
reviewer authored, plus the reasoning state produced by running some prefix of
that sequence through the engine, plus review-only metadata (name, tags, notes,
creation time). The reviewer builds the sequence one structured evidence item at
a time, runs items singly or all at once, inspects the engine's output after each
step, and can reset and rerun deterministically.

Phase 0 boundary: the authoritative input is a **structured EvidenceRecord**, not
free text. This module does no natural-language understanding and no evidence
extraction. It builds an ``EvidenceInput`` (the existing, unmodified Application
API DTO) from the reviewer's structured fields, relays the reviewer's structured
appraisal through the ``HarnessAppraiser`` port, and calls ``ReasoningService``.
All reasoning stays in the engine. Notes and tags are review metadata only and
are never sent into the engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
from sanuvia.adapters.support import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import (
    build_in_memory_dependencies,
    build_sqlite_dependencies,
)
from sanuvia.application.api import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.application.reasoning.core_loop import InteractionResult
from sanuvia.exit_test.session_state import SessionState, from_interactions
from sanuvia.domain import (
    EvidenceClass,
    EvidenceRecord,
    Hypothesis,
    HypothesisId,
    Inquiry,
    Prediction,
    ProvenanceRecord,
    RecognitionEvent,
    RevisionEvent,
    RevisionLedgerEntry,
    SubjectId,
    WorldModel,
)

from .appraiser import HarnessAppraiser

HARNESS_VERSION = "Persistent Reasoning Core (Phase 0) — review harness"
ENGINE_VERSION = "Persistent Reasoning Core (Phase 0)"
DEFAULT_SUBJECT = "review-subject"


@dataclass(frozen=True)
class ProposalInput:
    hypothesis_id: str
    statement: str
    initial_support: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "statement": self.statement,
            "initial_support": self.initial_support,
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "ProposalInput":
        return ProposalInput(
            hypothesis_id=str(d["hypothesis_id"]),
            statement=str(d.get("statement", "")),
            initial_support=float(d.get("initial_support", 0.4)),
        )


@dataclass(frozen=True)
class EvidenceSpec:
    """A complete, structured, canonical EvidenceRecord specification."""

    content: str
    evidence_class: str
    reliability: float
    classification_confidence: float = 0.9
    source: str = "review-harness"
    provenance_confidence: float = 1.0
    classification_status: str = ""
    metadata: tuple[tuple[str, str], ...] = ()
    supports: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    proposals: tuple[ProposalInput, ...] = field(default=())

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": self.content,
            "evidence_class": self.evidence_class,
            "reliability": self.reliability,
            "classification_confidence": self.classification_confidence,
            "source": self.source,
            "provenance_confidence": self.provenance_confidence,
            "classification_status": self.classification_status,
            "metadata": [list(pair) for pair in self.metadata],
            "supports": list(self.supports),
            "contradicts": list(self.contradicts),
            "proposals": [p.to_dict() for p in self.proposals],
        }

    @staticmethod
    def from_dict(d: dict[str, Any]) -> "EvidenceSpec":
        return EvidenceSpec(
            content=str(d["content"]),
            evidence_class=str(d.get("evidence_class", "behavioural")),
            reliability=float(d.get("reliability", 0.7)),
            classification_confidence=float(d.get("classification_confidence", 0.9)),
            source=str(d.get("source", "review-harness")),
            provenance_confidence=float(d.get("provenance_confidence", 1.0)),
            classification_status=str(d.get("classification_status", "")),
            metadata=tuple(
                (str(k), str(v)) for k, v in (tuple(m) for m in d.get("metadata", []))
            ),
            supports=tuple(str(s) for s in d.get("supports", [])),
            contradicts=tuple(str(c) for c in d.get("contradicts", [])),
            proposals=tuple(ProposalInput.from_dict(p) for p in d.get("proposals", [])),
        )


# --- display presenters (formatting only, no reasoning) -----------------------


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _meta_value(record: EvidenceRecord, key: str) -> str | None:
    for k, v in record.provenance.acquisition_metadata:
        if k == key:
            return v
    return None


def _evidence_dto(e: EvidenceRecord) -> dict[str, Any]:
    return {
        "id": e.id,
        "subject": e.subject_id,
        "class": e.evidence_class.value,
        "content": e.content,
        "source": e.provenance.source,
        "reliability": round(e.reliability.value, 3),
        "classification_confidence": round(e.classification_confidence.value, 3),
        "classification_status": _meta_value(e, "classification_status") or "—",
        "provenance_confidence": round(e.provenance.confidence.value, 3),
        "metadata": [list(pair) for pair in e.provenance.acquisition_metadata],
        "occurred_at": _iso(e.occurred_at),
    }


def _hypothesis_dto(h: Hypothesis) -> dict[str, Any]:
    return {
        "record_id": h.record_id,
        "hypothesis_id": h.hypothesis_id,
        "statement": h.statement,
        "support": round(h.support.value, 3),
        "supporting_evidence": list(h.supporting_evidence_ids),
        "contradicting_evidence": list(h.contradicting_evidence_ids),
        "evaluated_at_version": h.evaluated_at_version,
    }


def _prediction_dto(p: Prediction) -> dict[str, Any]:
    return {
        "id": p.id,
        "trajectory_kind": p.trajectory.kind.value,
        "description": p.trajectory.description,
        "likelihood": round(p.likelihood.value, 3),
        "from_hypotheses": list(p.derived_from_hypothesis_ids),
        "from_evidence": list(p.derived_from_evidence_ids),
        "model_version": p.model_version_id,
    }


def _inquiry_dto(inq: Inquiry) -> dict[str, Any]:
    return {
        "id": inq.id,
        "statement": inq.statement,
        "status": inq.status.value,
        "activated_hypotheses": list(inq.activated_hypothesis_ids),
        "motivating_evidence": list(inq.motivating_evidence_ids),
        "current_uncertainty": round(inq.current_uncertainty.value, 3),
    }


def _revision_event_dto(ev: RevisionEvent) -> dict[str, Any]:
    return {
        "id": ev.id,
        "outcome": ev.outcome.value,
        "affected": ev.affected_object_id,
        "triggering_evidence": list(ev.triggering_evidence_ids),
        "from_version": ev.from_model_version_id,
        "to_version": ev.to_model_version_id,
        "status": ev.status.value,
        "anomaly_resolution": ev.anomaly_resolution_id,
    }


def _ledger_dto(entry: RevisionLedgerEntry) -> dict[str, Any]:
    return {
        "sequence_no": entry.sequence_no,
        "appended_at": _iso(entry.appended_at),
        "event": _revision_event_dto(entry.revision_event),
    }


def _world_model_dto(m: WorldModel) -> dict[str, Any]:
    return {
        "version": m.model_version_id,
        "subject": m.subject_id,
        "reasoning_system_id": m.reasoning_system_id,
        "model_uncertainty": round(m.model_uncertainty.value, 3),
        "active_hypotheses": list(m.active_hypothesis_ids),
        "active_predictions": list(m.active_prediction_ids),
        "active_inquiries": list(m.active_inquiry_ids),
        "created_by_revision": m.created_by_revision_id,
        "provenance_record_id": m.provenance_record_id,
    }


def _provenance_dto(p: ProvenanceRecord) -> dict[str, Any]:
    return {
        "id": p.id,
        "traces_to_evidence": list(p.traces_to_evidence_ids),
        "traces_to_revisions": list(p.traces_to_revision_ids),
        "created_at": _iso(p.created_at),
    }


def _recognition_dto(r: RecognitionEvent) -> dict[str, Any]:
    return {
        "id": r.id,
        "kind": r.kind.value,
        "description": r.description,
        "supporting_evidence": list(r.supporting_evidence_ids),
        "model_version": r.model_version_id,
    }


class TestCase:
    """One deterministic reasoning experiment: an ordered EvidenceRecord
    sequence, the reasoning state produced by running it, and review metadata."""

    __test__ = False  # not a pytest test class despite the "Test" prefix

    def __init__(
        self,
        *,
        id: str,
        name: str,
        subject: str = DEFAULT_SUBJECT,
        backend: str = "memory",
        db_path: str = ":memory:",
        tags: list[str] | None = None,
        notes: list[str] | None = None,
        created_at: str | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.subject = SubjectId(subject)
        self.tags = list(tags or [])
        self.notes = list(notes or [])
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.last_exit_passed: bool | None = None
        self._backend = backend
        self._db_path = db_path
        self._sequence: list[EvidenceSpec] = []
        self._build()

    @classmethod
    def from_spec_dict(
        cls, d: dict[str, Any], *, backend: str, db_path: str
    ) -> "TestCase":
        case = cls(
            id=str(d["id"]),
            name=str(d.get("name", d["id"])),
            subject=str(d.get("subject", DEFAULT_SUBJECT)),
            backend=backend,
            db_path=db_path,
            tags=[str(t) for t in d.get("tags", [])],
            notes=[str(n) for n in d.get("notes", [])],
            created_at=d.get("created_at"),
        )
        case.load_sequence(
            [EvidenceSpec.from_dict(s) for s in d.get("evidence_specs", [])]
        )
        return case

    def _build(self) -> None:
        """(Re)create a clean engine + store; clears reasoning state, keeps the
        authored sequence and review metadata."""
        self._appraiser = HarnessAppraiser()
        self._clock = ManualClock()
        ids = SequentialIdGenerator()
        self._store: InMemoryReasoningStore | SqliteReasoningStore
        if self._backend == "sqlite":
            sqlite_store = SqliteReasoningStore(self._db_path)
            self._store = sqlite_store
            deps = build_sqlite_dependencies(
                store=sqlite_store, appraiser=self._appraiser,
                clock=self._clock, ids=ids,
            )
        else:
            memory_store = InMemoryReasoningStore()
            self._store = memory_store
            deps = build_in_memory_dependencies(
                store=memory_store, appraiser=self._appraiser,
                clock=self._clock, ids=ids,
            )
        self._service = ReasoningService(deps)
        self._history: list[InteractionResult] = []
        self._step_snapshots: list[dict[str, Any]] = []
        self._ran_count = 0
        self._last_result: InteractionResult | None = None

    # -- sequence & review metadata editing ---------------------------------

    @property
    def sequence(self) -> tuple[EvidenceSpec, ...]:
        return tuple(self._sequence)

    def add_evidence(self, spec: EvidenceSpec) -> None:
        self._sequence.append(spec)

    def load_sequence(self, specs: list[EvidenceSpec]) -> None:
        self._sequence = list(specs)

    def rename(self, name: str) -> None:
        self.name = name

    def set_tags(self, tags: list[str]) -> None:
        self.tags = [str(t) for t in tags]

    def add_note(self, text: str) -> None:
        self.notes.append(text)

    def remove_note(self, index: int) -> None:
        if 0 <= index < len(self.notes):
            del self.notes[index]

    # -- running ------------------------------------------------------------

    def _run_spec(self, spec: EvidenceSpec) -> None:
        self._clock.tick()  # deterministic, advancing timestamp
        self._appraiser.set_pending(
            Appraisal(
                supports=tuple(HypothesisId(s) for s in spec.supports),
                contradicts=tuple(HypothesisId(c) for c in spec.contradicts),
                proposals=tuple(
                    ProposedHypothesis(
                        hypothesis_id=HypothesisId(p.hypothesis_id),
                        statement=p.statement,
                        initial_support=p.initial_support,
                        supporting_evidence_ids=(),
                    )
                    for p in spec.proposals
                ),
            )
        )
        metadata = spec.metadata
        if spec.classification_status:
            metadata = metadata + (("classification_status", spec.classification_status),)
        evidence = EvidenceInput(
            subject_id=self.subject,
            evidence_class=EvidenceClass(spec.evidence_class),
            content=spec.content,
            source=spec.source,
            reliability=spec.reliability,
            classification_confidence=spec.classification_confidence,
            provenance_confidence=spec.provenance_confidence,
            acquisition_metadata=metadata,
        )
        self._last_result = self._service.record_interaction(self.subject, [evidence])
        self._history.append(self._last_result)

    def _advance(self, spec: EvidenceSpec) -> None:
        self._run_spec(spec)
        self._ran_count += 1
        self._step_snapshots.append(self.snapshot())

    def run_next(self) -> dict[str, Any]:
        if self._ran_count < len(self._sequence):
            self._advance(self._sequence[self._ran_count])
        return self.snapshot()

    def run_all(self) -> dict[str, Any]:
        self._build()
        for spec in self._sequence:
            self._advance(spec)
        return self.snapshot()

    def reset(self) -> dict[str, Any]:
        self._build()
        self.last_exit_passed = None
        return self.snapshot()

    # -- rendering handle ---------------------------------------------------

    def reasoning_state(self) -> SessionState:
        return from_interactions(self.subject, self._history, self._store)

    def spec_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "subject": str(self.subject),
            "tags": list(self.tags),
            "notes": list(self.notes),
            "created_at": self.created_at,
            "evidence_specs": [spec.to_dict() for spec in self._sequence],
        }

    # -- reads --------------------------------------------------------------

    def timeline(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, r in enumerate(self._history, start=1):
            before = len(r.competing_hypotheses_before)
            after = len(r.active_hypotheses)
            ingested = r.ingested_evidence
            out.append(
                {
                    "step": i,
                    "evidence_id": ingested[0].id if ingested else None,
                    "evidence_class": ingested[0].evidence_class.value if ingested else None,
                    "evidence_content": ingested[0].content if ingested else "",
                    "hypotheses_created": max(0, after - before),
                    "hypotheses_total": after,
                    "world_model_version": (
                        r.model.model_version_id if (r.committed and r.model) else None
                    ),
                    "committed": r.committed,
                    "inquiry": None if r.inquiry is None else r.inquiry.id,
                    "predictions": len(r.predictions),
                    "revision_events": len(r.revision_result.revision_events),
                    "uncertainty_before": (
                        None if r.model_uncertainty_before is None
                        else round(r.model_uncertainty_before, 3)
                    ),
                    "uncertainty_after": (
                        None if r.model_uncertainty is None
                        else round(r.model_uncertainty, 3)
                    ),
                }
            )
        return out

    def summary(self) -> dict[str, Any]:
        view = self._service.view()
        subject = self.subject
        model = view.current_model(subject)
        ledger = list(view.revision_history(subject))
        versions = {
            e.revision_event.to_model_version_id
            for e in ledger
            if e.revision_event.to_model_version_id is not None
        }
        return {
            "test_case_name": self.name,
            "evidence_records": len(view.evidence(subject)),
            "interactions_executed": self._ran_count,
            "world_model_versions": len(versions),
            "revision_events": len(ledger),
            "active_hypotheses": len(view.active_hypotheses(subject)),
            "predictions": len(view.active_predictions(subject)),
            "inquiries": len(view.active_inquiries(subject)),
            "model_uncertainty": (
                None if model is None else round(model.model_uncertainty.value, 3)
            ),
            "exit_test_status": self.last_exit_passed,
            "deterministic": True,
            "backend": self._backend,
            "engine_version": ENGINE_VERSION,
        }

    def snapshot_at(self, step: int) -> dict[str, Any]:
        if 1 <= step <= len(self._step_snapshots):
            return self._step_snapshots[step - 1]
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        view = self._service.view()
        subject = self.subject
        model = view.current_model(subject)

        provenance: dict[str, Any] | None = None
        if model is not None and model.provenance_record_id is not None:
            record = self._store.provenance.get(model.provenance_record_id)
            if record is not None:
                provenance = _provenance_dto(record)

        last = self._last_result
        revision_events = (
            [] if last is None else [
                _revision_event_dto(ev) for ev in last.revision_result.revision_events
            ]
        )
        anomalies = (
            [] if last is None else [
                {"id": a.id, "disposition": a.disposition.value,
                 "triggering_evidence": list(a.triggering_evidence_ids)}
                for a in last.revision_result.anomaly_resolutions
            ]
        )

        return {
            "metadata": self.metadata(),
            "summary": self.summary(),
            "timeline": self.timeline(),
            "notes": list(self.notes),
            "tags": list(self.tags),
            "sequence": self._sequence_dto(),
            "evidence": [_evidence_dto(e) for e in view.evidence(subject)],
            "world_model": None if model is None else _world_model_dto(model),
            "hypotheses": [_hypothesis_dto(h) for h in view.active_hypotheses(subject)],
            "predictions": [_prediction_dto(p) for p in view.active_predictions(subject)],
            "inquiries": [_inquiry_dto(i) for i in view.active_inquiries(subject)],
            "revision_events": revision_events,
            "anomaly_resolutions": anomalies,
            "revision_ledger": [
                _ledger_dto(e) for e in view.revision_history(subject)
            ],
            "model_uncertainty": (
                None if model is None else round(model.model_uncertainty.value, 3)
            ),
            "uncertainty_before": None if last is None else last.model_uncertainty_before,
            "provenance": provenance,
            "recognition_conditions": [
                _recognition_dto(r) for r in view.recognition_events(subject)
            ],
        }

    def _sequence_dto(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for i, spec in enumerate(self._sequence):
            ran = i < self._ran_count
            evidence_id: str | None = None
            if ran and i < len(self._history):
                ingested = self._history[i].ingested_evidence
                evidence_id = ingested[0].id if ingested else None
            out.append(
                {
                    "position": i + 1,
                    "evidence_class": spec.evidence_class,
                    "content": spec.content,
                    "reliability": spec.reliability,
                    "ran": ran,
                    "evidence_id": evidence_id,
                }
            )
        return out

    def metadata(self) -> dict[str, Any]:
        view = self._service.view()
        model = view.current_model(self.subject)
        return {
            "version": HARNESS_VERSION,
            "engine_version": ENGINE_VERSION,
            "test_case_id": self.id,
            "test_case_name": self.name,
            "subject": str(self.subject),
            "tags": list(self.tags),
            "created_at": self.created_at,
            "interactions_run": self._ran_count,
            "sequence_length": len(self._sequence),
            "world_model_version": None if model is None else model.model_version_id,
            "database": self._db_path if self._backend == "sqlite" else "in-memory",
            "backend": self._backend,
            "deterministic_mode": "on (ManualClock + SequentialIdGenerator)",
            "last_exit_passed": self.last_exit_passed,
        }
