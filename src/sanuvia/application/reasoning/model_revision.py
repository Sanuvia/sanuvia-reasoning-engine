"""The Model Revision engine — the central computational responsibility.

Given a batch of appraised evidence for one subject, it revises the persistent
model: it adjusts hypothesis support, opens/updates competing hypotheses, decides
anomaly dispositions for contradictions, produces traceable RevisionEvents,
commits them through the injected policy into a new immutable WorldModel version,
regenerates predictions, and raises an Inquiry when material uncertainty and
genuine competition warrant it.

What is genuine here (the invention): support/uncertainty revision, contradiction
handling, competing-hypothesis retention, versioning, provenance, prediction
grounding, and inquiry selection.

What is deliberately *not* decided here (deferred / assigned elsewhere, reached
only through ports so nothing is faked in the core):

* Which hypotheses evidence supports/contradicts, and new candidate explanations
  — the ``EvidenceAppraiser`` (a foundation model later).
* Whether a proposed revision commits — the ``RevisionCommitPolicy``
  (governance unresolved by the spec).
* Second-order revision for an ``ESCALATE`` disposition — not implemented; an
  escalation produces *no* RevisionEvent and only records the anomaly.
* Recognition-condition computation and inquiry reopening thresholds — not invoked.

Phase-0 heuristics (support arithmetic, thresholds, disposition-by-reliability)
live in :class:`ReasoningConfig` and are documented there as replaceable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sanuvia.domain import (
    AnomalyDisposition,
    AnomalyResolution,
    AnomalyResolutionId,
    CurrentModelSnapshot,
    DependencyEdge,
    DependencyEdgeId,
    DependencyRelation,
    EvidenceRecord,
    EvidenceRecordId,
    FutureTrajectory,
    Hypothesis,
    HypothesisId,
    HypothesisRecordId,
    HypothesisSupport,
    Inquiry,
    InquiryId,
    InquiryStatus,
    ModelRevisionResult,
    ModelUncertainty,
    ObjectRef,
    Prediction,
    PredictionId,
    PredictionLikelihood,
    ProvenanceRecord,
    ProvenanceRecordId,
    RevisionEvent,
    RevisionEventId,
    RevisionOutcome,
    RevisionStatus,
    SubjectId,
    TrajectoryKind,
    WorldModel,
    WorldModelVersionId,
)

from .dependencies import ReasoningDependencies
from .scoring import (
    aggregate_model_uncertainty,
    expected_information_gain,
    support_after_contradiction,
    support_after_support,
)


@dataclass(frozen=True)
class RevisionApplied:
    """Outcome of one revision over a batch of evidence."""

    model: WorldModel | None
    result: ModelRevisionResult
    predictions: tuple[Prediction, ...]
    inquiry: Inquiry | None
    committed: bool


@dataclass
class _Intent:
    """A proposed revision plus the hypothesis record it would write (if any)."""

    event: RevisionEvent
    record: Hypothesis | None


def _dedup(*groups: tuple[EvidenceRecordId, ...]) -> tuple[EvidenceRecordId, ...]:
    seen: dict[EvidenceRecordId, None] = {}
    for group in groups:
        for item in group:
            seen.setdefault(item, None)
    return tuple(seen)


@dataclass
class _RevisionRun:
    """Mutable context for a single ``revise`` call — keeps the reasoning
    methods free of long parameter lists."""

    deps: ReasoningDependencies
    subject_id: SubjectId
    from_version: WorldModelVersionId | None
    new_version_id: WorldModelVersionId
    now: datetime
    working: dict[HypothesisId, Hypothesis] = field(default_factory=dict)
    traj_hints: dict[HypothesisId, FutureTrajectory] = field(default_factory=dict)
    intents: list[_Intent] = field(default_factory=list)
    anomalies: list[AnomalyResolution] = field(default_factory=list)
    edges: list[DependencyEdge] = field(default_factory=list)

    # -- id helpers ---------------------------------------------------------

    def _hyp_record(
        self,
        *,
        hypothesis_id: HypothesisId,
        statement: str,
        support: float,
        supporting: tuple[EvidenceRecordId, ...],
        contradicting: tuple[EvidenceRecordId, ...],
        supersedes: HypothesisRecordId | None,
    ) -> Hypothesis:
        return Hypothesis(
            record_id=HypothesisRecordId(self.deps.ids.new_id("hyprec")),
            hypothesis_id=hypothesis_id,
            statement=statement,
            support=HypothesisSupport(max(0.0, min(1.0, support))),
            supporting_evidence_ids=supporting,
            contradicting_evidence_ids=contradicting,
            evaluated_at_version=self.new_version_id,
            evaluated_at=self.now,
            supersedes_record_id=supersedes,
        )

    def _event(
        self,
        *,
        affected: str,
        outcome: RevisionOutcome,
        evidence_id: EvidenceRecordId,
        anomaly_id: AnomalyResolutionId | None = None,
    ) -> RevisionEvent:
        return RevisionEvent(
            id=RevisionEventId(self.deps.ids.new_id("rev")),
            subject_id=self.subject_id,
            affected_object_id=ObjectRef(affected),
            outcome=outcome,
            triggering_evidence_ids=(evidence_id,),
            status=RevisionStatus.PROPOSED,
            created_at=self.now,
            from_model_version_id=self.from_version,
            anomaly_resolution_id=anomaly_id,
        )

    def _edge(
        self, frm: str, to: str, relation: DependencyRelation
    ) -> DependencyEdge:
        return DependencyEdge(
            id=DependencyEdgeId(self.deps.ids.new_id("dep")),
            from_ref=ObjectRef(frm),
            to_ref=ObjectRef(to),
            relation=relation,
            created_at=self.now,
        )

    # -- per-evidence handling ---------------------------------------------

    def ingest(self, evidence: EvidenceRecord) -> None:
        appraisal = self.deps.appraiser.appraise(
            self.subject_id, evidence, list(self.working.values())
        )
        for proposal in appraisal.proposals:
            record = self._hyp_record(
                hypothesis_id=proposal.hypothesis_id,
                statement=proposal.statement,
                support=proposal.initial_support,
                supporting=_dedup((evidence.id,), proposal.supporting_evidence_ids),
                contradicting=(),
                supersedes=None,
            )
            self.working[proposal.hypothesis_id] = record
            if proposal.predicted_trajectory is not None:
                self.traj_hints[proposal.hypothesis_id] = proposal.predicted_trajectory
            self.intents.append(
                _Intent(
                    self._event(
                        affected=proposal.hypothesis_id,
                        outcome=RevisionOutcome.HYPOTHESIZE,
                        evidence_id=evidence.id,
                    ),
                    record,
                )
            )
            self.edges.append(
                self._edge(evidence.id, proposal.hypothesis_id,
                           DependencyRelation.SUPPORTS)
            )

        for hid in appraisal.supports:
            prev = self.working.get(hid)
            if prev is None:
                continue  # cannot support an unknown hypothesis
            new_support = support_after_support(
                prev.support.value, evidence.reliability.value,
                self.deps.config.support_learning_rate,
            )
            record = self._hyp_record(
                hypothesis_id=hid,
                statement=prev.statement,
                support=new_support,
                supporting=_dedup(prev.supporting_evidence_ids, (evidence.id,)),
                contradicting=prev.contradicting_evidence_ids,
                supersedes=prev.record_id,
            )
            self.working[hid] = record
            self.intents.append(
                _Intent(
                    self._event(
                        affected=hid, outcome=RevisionOutcome.STRENGTHEN,
                        evidence_id=evidence.id,
                    ),
                    record,
                )
            )
            self.edges.append(
                self._edge(evidence.id, hid, DependencyRelation.SUPPORTS)
            )

        for hid in appraisal.contradicts:
            self._contradict(evidence, hid)

    def _contradict(self, evidence: EvidenceRecord, hid: HypothesisId) -> None:
        prev = self.working.get(hid)
        if prev is None:
            return
        cfg = self.deps.config
        established = prev.support.value >= cfg.established_support_threshold
        if not established:
            # Contradiction of a tentative idea: ordinary weakening, no anomaly.
            self._weaken(evidence, prev, anomaly_id=None)
            return

        # Contradiction against established understanding -> anomaly first
        # (FR-MR-004): disposition decided before any RevisionEvent.
        disposition = self._disposition(evidence.reliability.value)
        anomaly = AnomalyResolution(
            id=AnomalyResolutionId(self.deps.ids.new_id("anom")),
            subject_id=self.subject_id,
            disposition=disposition,
            triggering_evidence_ids=(evidence.id,),
            created_at=self.now,
            note=f"contradiction of established hypothesis {hid}",
        )
        self.anomalies.append(anomaly)
        if disposition is AnomalyDisposition.REVISE:
            self._weaken(evidence, prev, anomaly_id=anomaly.id)
        # ESCALATE (second-order, deferred) and REJECT produce no RevisionEvent:
        # the model holds for this hypothesis; only the anomaly is recorded.

    def _weaken(
        self,
        evidence: EvidenceRecord,
        prev: Hypothesis,
        *,
        anomaly_id: AnomalyResolutionId | None,
    ) -> None:
        cfg = self.deps.config
        new_support = support_after_contradiction(
            prev.support.value, evidence.reliability.value, cfg.support_learning_rate
        )
        crossed_out = (
            prev.support.value >= cfg.established_support_threshold
            and new_support < cfg.established_support_threshold
        )
        outcome = (
            RevisionOutcome.CONTRADICT if crossed_out else RevisionOutcome.WEAKEN
        )
        record = self._hyp_record(
            hypothesis_id=prev.hypothesis_id,
            statement=prev.statement,
            support=new_support,
            supporting=prev.supporting_evidence_ids,
            contradicting=_dedup(prev.contradicting_evidence_ids, (evidence.id,)),
            supersedes=prev.record_id,
        )
        self.working[prev.hypothesis_id] = record
        self.intents.append(
            _Intent(
                self._event(
                    affected=prev.hypothesis_id, outcome=outcome,
                    evidence_id=evidence.id, anomaly_id=anomaly_id,
                ),
                record,
            )
        )
        self.edges.append(
            self._edge(evidence.id, prev.hypothesis_id,
                       DependencyRelation.CONTRADICTS)
        )

    def _disposition(self, reliability: float) -> AnomalyDisposition:
        cfg = self.deps.config
        if reliability >= cfg.contradiction_revise_reliability:
            return AnomalyDisposition.REVISE
        if reliability >= cfg.contradiction_reject_reliability:
            return AnomalyDisposition.ESCALATE  # insufficient basis; second-order
        return AnomalyDisposition.REJECT


class ModelRevisionEngine:
    """Revises the persistent model in response to appraised evidence."""

    def __init__(self, deps: ReasoningDependencies) -> None:
        self._d = deps

    def revise(
        self,
        subject_id: SubjectId,
        evidence_batch: tuple[EvidenceRecord, ...],
        current_model: WorldModel | None,
    ) -> RevisionApplied:
        d = self._d
        now = d.clock.now()
        run = _RevisionRun(
            deps=d,
            subject_id=subject_id,
            from_version=(
                current_model.model_version_id if current_model is not None else None
            ),
            # Reserve the id this revision *would* produce (opaque; harmless if
            # nothing commits).
            new_version_id=WorldModelVersionId(d.ids.new_id("wm")),
            now=now,
            working={
                h.hypothesis_id: h
                for h in d.hypotheses.list_for_subject(subject_id)
            },
        )

        for evidence in evidence_batch:
            run.ingest(evidence)

        # Anomaly resolutions are recorded regardless of whether a revision
        # committed — the disposition itself is part of the authoritative record.
        for anomaly in run.anomalies:
            d.anomalies.add(anomaly)

        committed_intents = [
            i for i in run.intents if d.commit_policy.should_commit(i.event)
        ]
        if not committed_intents:
            # Nothing committed: the model holds (FR-MR-003). Evidence and any
            # anomaly resolutions are still recorded; understanding is unchanged.
            return RevisionApplied(
                model=current_model,
                result=ModelRevisionResult(
                    subject_id=subject_id,
                    revision_events=(),
                    anomaly_resolutions=tuple(run.anomalies),
                    new_model_version_id=None,
                ),
                predictions=(),
                inquiry=None,
                committed=False,
            )

        committed_events: list[RevisionEvent] = []
        for intent in committed_intents:
            if intent.record is not None:
                d.hypotheses.add(intent.record)
            event = intent.event.committed(run.new_version_id)
            d.ledger.append(event)
            committed_events.append(event)
        for edge in run.edges:
            d.dependencies.add_edge(edge)

        active = list(d.hypotheses.list_for_subject(subject_id))
        supports = [h.support.value for h in active]
        model_uncertainty = aggregate_model_uncertainty(supports)

        predictions = self._regenerate_predictions(active, run)
        inquiry = self._maybe_open_inquiry(
            subject_id, active, supports, model_uncertainty, committed_events, now
        )

        provenance = ProvenanceRecord(
            id=ProvenanceRecordId(d.ids.new_id("prov")),
            subject_id=subject_id,
            traces_to_evidence_ids=tuple(e.id for e in evidence_batch),
            traces_to_revision_ids=tuple(e.id for e in committed_events),
            created_at=now,
        )
        d.provenance.add(provenance)

        model = WorldModel(
            model_version_id=run.new_version_id,
            subject_id=subject_id,
            reasoning_system_id=d.reasoning_system_id,
            model_uncertainty=ModelUncertainty(model_uncertainty),
            active_hypothesis_ids=tuple(h.hypothesis_id for h in active),
            active_prediction_ids=tuple(p.id for p in predictions),
            active_inquiry_ids=(inquiry.id,) if inquiry is not None else (),
            created_at=now,
            created_by_revision_id=committed_events[0].id,
            provenance_record_id=provenance.id,
        )
        d.world_models.append_version(model)
        d.world_models.set_current_pointer(
            CurrentModelSnapshot(
                subject_id=subject_id,
                model_version_id=run.new_version_id,
                committed_at=now,
            )
        )

        return RevisionApplied(
            model=model,
            result=ModelRevisionResult(
                subject_id=subject_id,
                revision_events=tuple(committed_events),
                anomaly_resolutions=tuple(run.anomalies),
                new_model_version_id=run.new_version_id,
            ),
            predictions=predictions,
            inquiry=inquiry,
            committed=True,
        )

    def _regenerate_predictions(
        self, active: list[Hypothesis], run: _RevisionRun
    ) -> tuple[Prediction, ...]:
        cfg = self._d.config
        # A trajectory kind, once established for a hypothesis, carries forward
        # across versions. (Full prediction lifecycle governance — creation,
        # expiry, confirmation — is spec-unresolved and kept minimal here.)
        prior_trajectory: dict[HypothesisId, FutureTrajectory] = {}
        for prior in self._d.predictions.list_for_subject(run.subject_id):
            for hid in prior.derived_from_hypothesis_ids:
                prior_trajectory[hid] = prior.trajectory

        predictions: list[Prediction] = []
        for h in active:
            if h.support.value < cfg.prediction_support_threshold:
                continue  # below threshold -> any prior prediction is invalidated
            trajectory = (
                run.traj_hints.get(h.hypothesis_id)
                or prior_trajectory.get(h.hypothesis_id)
                or FutureTrajectory(
                    kind=TrajectoryKind.OBSERVED_TRAJECTORY,
                    description=f"trajectory consistent with: {h.statement}",
                )
            )
            prediction = Prediction(
                id=PredictionId(self._d.ids.new_id("pred")),
                trajectory=trajectory,
                likelihood=PredictionLikelihood(h.support.value),
                derived_from_hypothesis_ids=(h.hypothesis_id,),
                derived_from_evidence_ids=h.supporting_evidence_ids,
                model_version_id=run.new_version_id,
                created_at=run.now,
            )
            self._d.predictions.add(prediction)
            predictions.append(prediction)
            self._d.dependencies.add_edge(
                run._edge(prediction.id, h.hypothesis_id,
                          DependencyRelation.DERIVED_FROM)
            )
        return tuple(predictions)

    def _maybe_open_inquiry(
        self,
        subject_id: SubjectId,
        active: list[Hypothesis],
        supports: list[float],
        model_uncertainty: float,
        committed_events: list[RevisionEvent],
        now: datetime,
    ) -> Inquiry | None:
        cfg = self._d.config
        if model_uncertainty < cfg.inquiry_uncertainty_threshold:
            return None
        if expected_information_gain(supports) <= 0.0:
            return None  # no genuine competition to resolve
        top = sorted(active, key=lambda h: h.support.value, reverse=True)[:2]
        if len(top) < 2:
            return None
        motivating = _dedup(*[h.supporting_evidence_ids for h in top])
        inquiry = Inquiry(
            id=InquiryId(self._d.ids.new_id("inq")),
            subject_id=subject_id,
            statement=(
                "Which explanation better fits the evidence: "
                f"'{top[0].statement}' or '{top[1].statement}'?"
            ),
            status=InquiryStatus.PROPOSED,
            activated_hypothesis_ids=tuple(h.hypothesis_id for h in top),
            motivating_evidence_ids=motivating,
            current_uncertainty=ModelUncertainty(model_uncertainty),
            created_at=now,
            produced_by_revision_id=(
                committed_events[0].id if committed_events else None
            ),
        )
        self._d.inquiries.add(inquiry)
        return inquiry
