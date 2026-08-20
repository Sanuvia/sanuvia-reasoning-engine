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
        dataset_id: str | None = None,
        expectations: list[dict[str, Any]] | None = None,
        dataset_purpose: dict[str, Any] | None = None,
    ) -> None:
        self.id = id
        self.name = name
        self.subject = SubjectId(subject)
        self.tags = list(tags or [])
        self.notes = list(notes or [])
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        # review metadata only (never sent to the engine): documented expected
        # per-step evolution for Review Dataset cases, the source dataset id, and
        # the dataset purpose shown before running.
        self.dataset_id = dataset_id
        self.expectations = list(expectations or [])
        self.dataset_purpose = dataset_purpose
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
            dataset_id=d.get("dataset_id"),
            expectations=d.get("expectations") or d.get("step_expectations"),
            dataset_purpose=d.get("dataset_purpose") or d.get("purpose_block"),
        )
        case.load_sequence(
            [EvidenceSpec.from_dict(s) for s in d.get("evidence_specs", [])]
        )
        return case

    def _build(self) -> None:
        """(Re)create a clean engine + store; clears reasoning state, keeps the
        authored sequence and review metadata.

        A Test Case is a *deterministic* experiment: it uses ``ManualClock`` +
        ``SequentialIdGenerator`` so a rerun reproduces byte-identically. Against
        the durable SQLite backend those ids restart at ``evidence-1`` on every
        rebuild, so the database must be cleared first — otherwise a rerun
        collides with rows persisted by the previous run (Finding 2). This
        ``reset()`` is a TEST-HARNESS lifecycle operation; durable production
        reasoning is never reset (it uses collision-safe ids and only appends)."""
        self._appraiser = HarnessAppraiser()
        self._clock = ManualClock()
        ids = SequentialIdGenerator()
        self._store: InMemoryReasoningStore | SqliteReasoningStore
        if self._backend == "sqlite":
            sqlite_store = SqliteReasoningStore(self._db_path)
            sqlite_store.reset()  # clear durable rows so the deterministic rerun is clean
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
            "dataset_id": self.dataset_id,
            "expectations": list(self.expectations),
            "dataset_purpose": self.dataset_purpose,
            "evidence_specs": [spec.to_dict() for spec in self._sequence],
        }

    # -- review analyses (all derived from engine outputs; no reasoning) ----

    def hypothesis_evolution(self) -> dict[str, Any]:
        """Each hypothesis's support at every step (None before it exists)."""
        order: list[str] = []
        seen: set[str] = set()
        per_step: list[dict[str, float]] = []
        for r in self._history:
            m = {str(h.hypothesis_id): round(h.support.value, 3) for h in r.active_hypotheses}
            for hid in m:
                if hid not in seen:
                    seen.add(hid)
                    order.append(hid)
            per_step.append(m)
        n = len(per_step)
        return {
            "steps": n,
            "series": [
                {
                    "hypothesis_id": hid,
                    "support": [per_step[i].get(hid) for i in range(n)],
                }
                for hid in order
            ],
        }

    def prediction_lifecycle(self) -> list[dict[str, Any]]:
        """Created / strengthened / weakened / invalidated events per hypothesis,
        by committed version."""
        prev: dict[str, float] = {}
        events: dict[str, list[dict[str, Any]]] = {}
        for i, r in enumerate(self._history, start=1):
            if not r.committed or r.model is None:
                continue  # held step: predictions unchanged
            version = r.model.model_version_id
            cur = {
                str(p.derived_from_hypothesis_ids[0]): round(p.likelihood.value, 3)
                for p in r.predictions
                if p.derived_from_hypothesis_ids
            }
            for hid, lk in cur.items():
                bucket = events.setdefault(hid, [])
                if hid not in prev:
                    bucket.append({"event": "created", "version": version, "likelihood": lk, "step": i})
                elif lk > prev[hid]:
                    bucket.append({"event": "strengthened", "version": version, "likelihood": lk, "step": i})
                elif lk < prev[hid]:
                    bucket.append({"event": "weakened", "version": version, "likelihood": lk, "step": i})
            for hid in prev:
                if hid not in cur:
                    events.setdefault(hid, []).append(
                        {"event": "invalidated", "version": version, "step": i}
                    )
            prev = cur
        return [{"hypothesis_id": hid, "events": evs} for hid, evs in events.items()]

    def world_model_timeline(self) -> list[dict[str, Any]]:
        """One node per committed version with its key state."""
        out: list[dict[str, Any]] = []
        for i, r in enumerate(self._history, start=1):
            if r.committed and r.model is not None:
                out.append(
                    {
                        "step": i,
                        "version": r.model.model_version_id,
                        "uncertainty": (
                            None if r.model_uncertainty is None
                            else round(r.model_uncertainty, 3)
                        ),
                        "active_hypotheses": [h.hypothesis_id for h in r.active_hypotheses],
                        "prediction_count": len(r.predictions),
                        "inquiry_count": 1 if r.inquiry is not None else 0,
                        "triggered_evidence": [e.id for e in r.ingested_evidence],
                    }
                )
        return out

    def revisions_by_interaction(self) -> list[dict[str, Any]]:
        """RevisionEvents grouped by the interaction that produced them."""
        out: list[dict[str, Any]] = []
        for i, r in enumerate(self._history, start=1):
            out.append(
                {
                    "step": i,
                    "evidence": [e.id for e in r.ingested_evidence],
                    "committed": r.committed,
                    "version": (
                        r.model.model_version_id if (r.committed and r.model) else None
                    ),
                    "revisions": [
                        {"id": ev.id, "outcome": ev.outcome.value,
                         "affected": ev.affected_object_id}
                        for ev in r.revision_result.revision_events
                    ],
                    "anomalies": [
                        {"id": a.id, "disposition": a.disposition.value}
                        for a in r.revision_result.anomaly_resolutions
                    ],
                    "hypothesized": [
                        ev.affected_object_id
                        for ev in r.revision_result.revision_events
                        if ev.outcome.value == "hypothesize"
                    ],
                }
            )
        return out

    def evidence_chains(self) -> list[dict[str, Any]]:
        """Per evidence record: the revisions it triggered, the version(s) it
        produced, and the predictions/inquiries in those versions."""
        view = self._service.view()
        subject = self.subject
        ver_predictions: dict[str, list[str]] = {}
        ver_inquiry: dict[str, str] = {}
        for r in self._history:
            if r.committed and r.model is not None:
                v = r.model.model_version_id
                ver_predictions[v] = [p.id for p in r.predictions]
                if r.inquiry is not None:
                    ver_inquiry[v] = r.inquiry.id
        chains: list[dict[str, Any]] = []
        ledger = list(view.revision_history(subject))
        for e in view.evidence(subject):
            revs = [
                {"id": x.revision_event.id, "outcome": x.revision_event.outcome.value,
                 "affected": x.revision_event.affected_object_id,
                 "version": x.revision_event.to_model_version_id}
                for x in ledger
                if e.id in x.revision_event.triggering_evidence_ids
            ]
            versions = []
            for rv in revs:
                if rv["version"] and rv["version"] not in versions:
                    versions.append(rv["version"])
            preds = [p for v in versions for p in ver_predictions.get(v, [])]
            inqs = [ver_inquiry[v] for v in versions if v in ver_inquiry]
            chains.append(
                {
                    "evidence_id": e.id,
                    "evidence_class": e.evidence_class.value,
                    "content": e.content,
                    "revisions": revs,
                    "versions": versions,
                    "predictions": preds,
                    "inquiries": inqs,
                }
            )
        return chains

    def verdict(self) -> dict[str, Any]:
        """Auto-generated reasoning-correctness verdict from engine outputs.

        These are Blueprint invariants that must hold for any correct run; they
        read only what the engine produced (no reasoning, no re-derivation)."""
        view = self._service.view()
        subject = self.subject
        if not self._history:
            return {"overall": "PENDING", "checks": []}
        ledger = list(view.revision_history(subject))
        model = view.current_model(subject)

        # hypotheses retained: no hypothesis disappears once introduced
        seen: set[str] = set()
        retained = True
        for r in self._history:
            cur = {str(h.hypothesis_id) for h in r.active_hypotheses}
            if any(h not in cur for h in seen):
                retained = False
            seen |= cur

        # uncertainty tracked: present and revised across versions
        us = [round(r.model_uncertainty, 3) for r in self._history if r.model_uncertainty is not None]
        uncertainty_ok = bool(us) and (len(set(us)) > 1 or len(us) == 1)

        # predictions grounded: every active prediction traces to hypothesis+version
        preds = view.active_predictions(subject)
        grounded = all(p.derived_from_hypothesis_ids and p.model_version_id for p in preds)

        # provenance preserved: current model has provenance; revisions cite evidence
        prov_ok = (model is None) or (
            model.provenance_record_id is not None
            and all(x.revision_event.triggering_evidence_ids for x in ledger)
        )

        # immutable model respected: append-only, contiguous, all committed
        seqs = [x.sequence_no for x in ledger]
        immutable = seqs == list(range(len(ledger))) and all(
            x.revision_event.status.value == "committed" for x in ledger
        )

        checks = [
            {"label": "competing hypotheses retained", "pass": retained},
            {"label": "uncertainty revised", "pass": uncertainty_ok},
            {"label": "predictions grounded in hypotheses", "pass": grounded},
            {"label": "provenance preserved", "pass": prov_ok},
            {"label": "immutable model respected", "pass": immutable},
        ]
        overall = "PASS" if all(c["pass"] for c in checks) else "FAIL"
        return {"overall": overall, "checks": checks}

    def expected_vs_actual(self) -> list[dict[str, Any]] | None:
        """Per-step Expected vs Actual comparison for Review Dataset cases."""
        if not self.expectations or not self._step_snapshots:
            return None
        # expected cumulative hypotheses from authored proposals
        cumulative: list[str] = []
        seen: set[str] = set()
        expected_hyps_by_step: list[list[str]] = []
        for spec in self._sequence:
            for p in spec.proposals:
                if p.hypothesis_id not in seen:
                    seen.add(p.hypothesis_id)
                    cumulative.append(p.hypothesis_id)
            expected_hyps_by_step.append(list(cumulative))

        rows: list[dict[str, Any]] = []
        prev_u: float | None = None
        for i, snap in enumerate(self._step_snapshots):
            exp = self.expectations[i] if i < len(self.expectations) else {}
            wm = snap["world_model"]
            actual_version = None if wm is None else wm["version"]
            actual_inquiry = bool(snap["inquiries"])
            actual_preds = sorted({p["from_hypotheses"][0] for p in snap["predictions"]})
            actual_hyps = sorted(h["hypothesis_id"] for h in snap["hypotheses"])
            u = snap["model_uncertainty"]
            if prev_u is None:
                actual_trend = "first"
            elif u > prev_u + 1e-9:
                actual_trend = "up"
            elif u < prev_u - 1e-9:
                actual_trend = "down"
            else:
                actual_trend = "flat"
            prev_u = u
            exp_hyps = sorted(expected_hyps_by_step[i]) if i < len(expected_hyps_by_step) else []

            def cmp(exp_v: Any, act_v: Any) -> dict[str, Any]:
                return {"expected": exp_v, "actual": act_v, "match": exp_v == act_v}

            fields = {
                "version": cmp(exp.get("version"), actual_version),
                "hypotheses": cmp(exp_hyps, actual_hyps),
                "uncertainty_trend": cmp(exp.get("uncertainty"), actual_trend),
                "prediction": cmp(sorted(exp.get("predictions", [])), actual_preds),
                "inquiry": cmp(exp.get("inquiry"), actual_inquiry),
            }
            rows.append(
                {
                    "step": i + 1,
                    "fields": fields,
                    "match": all(f["match"] for f in fields.values()),
                }
            )
        return rows

    def reasoning_summary(self) -> str:
        """A concise, deterministic engineering narrative built from reasoning
        state — templated from actual values, never hardcoded, no randomness."""
        if not self._history:
            return "No interactions have been run yet."
        view = self._service.view()
        subject = self.subject
        series = self.hypothesis_evolution()["series"]

        parts: list[str] = []
        initial = [h.hypothesis_id for h in self._history[0].active_hypotheses]
        if len(initial) >= 2:
            parts.append(
                f"The evidence initially supported {len(initial)} competing "
                f"explanations ({', '.join(sorted(initial))})."
            )
        elif len(initial) == 1:
            parts.append(f"The evidence initially suggested a single explanation ({initial[0]}).")

        gained, weakened = [], []
        for s in series:
            vals = [v for v in s["support"] if v is not None]
            if len(vals) >= 2 and vals[-1] > vals[0] + 1e-9:
                gained.append((s["hypothesis_id"], vals[0], vals[-1]))
            elif len(vals) >= 2 and vals[-1] < vals[0] - 1e-9:
                weakened.append((s["hypothesis_id"], vals[0], vals[-1]))
        if gained:
            parts.append(
                "As evidence accumulated, "
                + ", ".join(f"{h} gained support ({a}→{b})" for h, a, b in gained)
                + ("; " if weakened else ".")
            )
        if weakened:
            prefix = "" if gained else "As evidence accumulated, "
            parts.append(
                prefix
                + ", ".join(f"{h} weakened ({a}→{b})" for h, a, b in weakened)
                + "."
            )

        us = [round(r.model_uncertainty, 3) for r in self._history if r.model_uncertainty is not None]
        if len(us) >= 2:
            if us[-1] < us[0] - 1e-9:
                monotone = all(us[i + 1] <= us[i] + 1e-9 for i in range(len(us) - 1))
                word = "consistently decreased" if monotone else "decreased overall"
                parts.append(f"Model uncertainty {word} ({us[0]}→{us[-1]}).")
            elif us[-1] > us[0] + 1e-9:
                parts.append(f"Model uncertainty increased overall ({us[0]}→{us[-1]}).")
            else:
                parts.append(f"Model uncertainty remained around {us[-1]}.")

        pred_hyps = sorted({
            p.derived_from_hypothesis_ids[0]
            for p in view.active_predictions(subject)
            if p.derived_from_hypothesis_ids
        })
        if pred_hyps:
            parts.append("Predictions converged toward " + ", ".join(pred_hyps) + ".")
        else:
            parts.append("No predictions are currently active.")

        parts.append(
            "An inquiry remains open."
            if view.active_inquiries(subject)
            else "No inquiry remained."
        )
        parts.append(
            "The engine behaved consistently with the supplied evidence."
            if self.verdict()["overall"] == "PASS"
            else "Review the differences above."
        )
        return " ".join(parts)

    def explain_why(self) -> list[dict[str, Any]]:
        """For each currently dominant hypothesis, why it leads — entirely from
        engine state (supporting/contradicting evidence, support progression)."""
        view = self._service.view()
        subject = self.subject
        active = list(view.active_hypotheses(subject))
        if not active:
            return []
        series = {s["hypothesis_id"]: s["support"] for s in self.hypothesis_evolution()["series"]}
        pred_hyps = {
            p.derived_from_hypothesis_ids[0]
            for p in view.active_predictions(subject)
            if p.derived_from_hypothesis_ids
        }
        winners = [h for h in active if h.hypothesis_id in pred_hyps]
        if not winners:
            winners = [max(active, key=lambda h: h.support.value)]

        others_weakened = any(
            len([v for v in series.get(h.hypothesis_id, []) if v is not None]) >= 2
            and [v for v in series[h.hypothesis_id] if v is not None][-1]
            < [v for v in series[h.hypothesis_id] if v is not None][0] - 1e-9
            for h in active
        )
        out: list[dict[str, Any]] = []
        for h in sorted(winners, key=lambda x: x.support.value, reverse=True):
            prog = [v for v in series.get(h.hypothesis_id, []) if v is not None]
            n_support = len(h.supporting_evidence_ids)
            reason = f"Received {n_support} piece(s) of strengthening evidence"
            if others_weakened:
                reason += " while competing explanations weakened"
            reason += "."
            out.append({
                "hypothesis_id": h.hypothesis_id,
                "statement": h.statement,
                "supporting_evidence": list(h.supporting_evidence_ids),
                "contradicting_evidence": list(h.contradicting_evidence_ids),
                "support_progression": prog,
                "current_support": round(h.support.value, 3),
                "reason": reason,
            })
        return out

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
            # review analyses (all derived from engine outputs; no reasoning)
            "verdict": self.verdict(),
            "reasoning_summary": self.reasoning_summary(),
            "explain_why": self.explain_why(),
            "dataset_purpose": self.dataset_purpose,
            "hypothesis_evolution": self.hypothesis_evolution(),
            "prediction_lifecycle": self.prediction_lifecycle(),
            "world_model_timeline": self.world_model_timeline(),
            "revisions_by_interaction": self.revisions_by_interaction(),
            "evidence_chains": self.evidence_chains(),
            "expected_vs_actual": self.expected_vs_actual(),
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
