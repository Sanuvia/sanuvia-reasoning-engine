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

from sanuvia.application.ports.reasoning import AppraisalRequest
from sanuvia.domain import (
    DEFAULT_SPACE_ID,
    GovernedOutcome,
    GovernedRejection,
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
    SpaceId,
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
    space_id: SpaceId = DEFAULT_SPACE_ID
    working: dict[HypothesisId, Hypothesis] = field(default_factory=dict)
    traj_hints: dict[HypothesisId, FutureTrajectory] = field(default_factory=dict)
    intents: list[_Intent] = field(default_factory=list)
    anomalies: list[AnomalyResolution] = field(default_factory=list)
    edges: list[DependencyEdge] = field(default_factory=list)
    # -- semantic-state products of this run (nothing here is written) -------
    #: Hypotheses active when the interaction began. Handles are minted only for
    #: these, so a lineage created earlier in the same interaction is not visible
    #: to a later appraisal call (F-18); the in-flight MATCH_EXISTING arm absorbs
    #: the identity consequence.
    entering: tuple[Hypothesis, ...] = ()
    #: Deterministic arm only; R1 stays Slice 2 and is never wired here.
    adjudicator: object = None
    #: Committed lineage views, keyed by the immutable (subject, attribution).
    committed_views: dict = field(default_factory=dict)
    #: Plan-local lineage key -> list[LineageView], for in-flight adjudication
    #: (§2 G). A list because one bound admits several lineages (M-2).
    in_flight: dict = field(default_factory=dict)
    lineages: list = field(default_factory=list)
    statement_versions: list = field(default_factory=list)
    adjudications: list = field(default_factory=list)
    appraised: list = field(default_factory=list)
    decisions: list = field(default_factory=list)

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
            subject_id=self.subject_id,
            statement=statement,
            support=HypothesisSupport(max(0.0, min(1.0, support))),
            supporting_evidence_ids=supporting,
            contradicting_evidence_ids=contradicting,
            evaluated_at_version=self.new_version_id,
            evaluated_at=self.now,
            supersedes_record_id=supersedes,
            space_id=self.space_id,
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
            space_id=self.space_id,
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
        """Appraise one admitted record and extend the plan. Writes nothing.

        Sequence steps 3-8 (Technical Design v1.5.4 §3.1), once per admitted
        **appraisable** record. A ``RESPONSE_OR_RESONANCE`` or
        ``META_INSTRUCTION`` record receives no appraisal call at all (ruling
        Q1), which is what structurally closes every support-changing path for
        it -- there is no proposal or bearing to validate because none exists.
        """
        from sanuvia.application.reasoning import handles as _handles
        from sanuvia.application.reasoning.identity import LineageView
        from sanuvia.application.reasoning.plan_validation import AppraisedObservation
        from sanuvia.domain import IdentityOutcome

        standing = evidence.standing
        if standing is not None and not standing.is_appraisable:
            # Admitted and preserved; never appraised (Q1).
            return

        # M-6: the governed request identifier is allocated through the
        # injected IdGenerator, never ad-hoc. Two reasons, both governed rather
        # than cosmetic. It must be deterministic, so an identical run is
        # byte-reproducible -- a uuid4 made every request id differ between two
        # otherwise identical runs, and request ids appear in handles and in
        # every governed rejection message. And it must participate in the
        # snapshot/restore boundary (F-4, F-6): a rejected plan must not
        # permanently consume an identifier, which only holds if allocation goes
        # through the generator the UnitOfWork restores.
        request_id = self.deps.ids.new_id("req")
        participants = self._participants_for(evidence)
        table = _handles.build_table(
            request_id=request_id,
            observation=evidence,
            active_hypotheses=list(self.entering),
            candidates=[],
            participants=participants,
        )
        obs_view, hyp_views, cand_views = _handles.build_request_views(
            table=table,
            observation=evidence,
            active_hypotheses=list(self.entering),
            candidates=[],
            signatures=self._signature_views(table),
        )
        request = AppraisalRequest(
            request_id=request_id,
            subject_id=self.subject_id,
            space_id=self.space_id,
            observation=obs_view,
            existing=hyp_views,
            divergence_candidates=cand_views,
            participants=tuple(table.participants),
            observation_id=evidence.id,
        )
        response = self.deps.appraiser.appraise(request)

        # -- step 6: authoritative handle resolution -------------------------
        bearings: list[tuple[HypothesisId, object]] = []
        for bearing in response.bearings:
            bearings.append((table.resolve_hypothesis(str(bearing.target)), bearing.kind))

        # -- step 8: identity adjudication, before any durable id ------------
        decisions: dict[str, tuple[str, HypothesisId | None]] = {}
        for proposal in response.proposals:
            if not proposal.statement or not proposal.statement.strip():
                raise GovernedRejection(
                    GovernedOutcome.STATEMENT_CAPTURE_FAILURE,
                    f"proposal {proposal.local_ref!r} carries no statement",
                    references=(proposal.local_ref,),
                    raw_response=response.raw_response,
                )
            signature = self._resolve_signature(proposal, table)
            decision = self.adjudicator.adjudicate(
                proposal, signature,
                committed=self.committed_views, in_flight=self.in_flight,
            )
            self.decisions.append((decision, signature, proposal, evidence))
            decisions[proposal.local_ref] = (
                decision.outcome.value, decision.matched_hypothesis_id
            )
            self._apply_decision(decision, signature, proposal, evidence)

        self.appraised.append(
            AppraisedObservation(
                evidence_id=evidence.id, table=table,
                proposals=response.proposals, bearings=response.bearings,
                divergences=response.divergences,
                raw_response=response.raw_response, decisions=decisions,
            )
        )

        # -- support-axis bearings ------------------------------------------
        from sanuvia.application.ports.reasoning import BearingKind
        for hid, kind in bearings:
            if kind is BearingKind.SUPPORTS:
                self._strengthen(evidence, hid)
            elif kind is BearingKind.CONTRADICTS:
                self._contradict(evidence, hid)
            elif kind is BearingKind.WEAKENS:
                prev = self.working.get(hid)
                if prev is not None:
                    self._weaken(evidence, prev, anomaly_id=None)

    # -- adjudication helpers ----------------------------------------------

    def _participants_for(self, evidence: EvidenceRecord) -> list:
        """Participant ids this request may reference.

        Standing supplies them when present. Phase 0 records carry no standing,
        so the modelling subject is offered as a participant -- which is
        assumption A1 in the Scripted migration, surfaced here rather than
        hidden in the adapter.
        """
        from sanuvia.domain import ParticipantId
        found: list = []
        st = evidence.standing
        if st is not None:
            if st.source_id:
                found.append(st.source_id)
            if st.subject_id:
                found.append(st.subject_id)
        if not found:
            found.append(ParticipantId(str(self.subject_id)))
        return found

    def _signature_views(self, table) -> dict:
        """Signature projections for the hypotheses offered to the appraiser."""
        from sanuvia.application.ports.reasoning import CommitmentSignatureView
        from sanuvia.domain import ClaimClass, Stance
        label = next(iter(table.participants), None)
        views = {}
        for hid in table.hypotheses.values():
            lineage = self.deps_lineage(hid)
            if lineage is not None and label is not None:
                views[hid] = CommitmentSignatureView(
                    subject=label, attribution=lineage.attribution,
                    claim_class=ClaimClass.INTERPRETATION, stance=Stance.OPEN,
                )
            elif label is not None:
                views[hid] = CommitmentSignatureView(
                    subject=label, attribution=str(hid),
                    claim_class=ClaimClass.INTERPRETATION, stance=Stance.OPEN,
                )
        return views

    def deps_lineage(self, hid: HypothesisId):
        store = getattr(self.deps, "lineages", None)
        return store.get(hid) if store is not None else None

    def _resolve_signature(self, proposal, table):
        """Resolve a model-facing signature view into the durable value object.

        The ``subject`` label resolves through the request's table, so the model
        cannot mint a participant and cannot silently re-attribute a commitment.
        """
        from sanuvia.domain import CommitmentSignature
        view = proposal.signature
        subject = table.resolve_participant(str(view.subject))
        return CommitmentSignature(
            subject=subject, attribution=view.attribution,
            claim_class=view.claim_class, stance=view.stance,
            temporal_scope=view.temporal_scope,
        )

    def _apply_decision(self, decision, signature, proposal, evidence) -> None:
        """Turn an identity decision into plan entries. Still no writes."""
        from sanuvia.application.reasoning.identity import LineageView
        from sanuvia.domain import (
            AdjudicationStatus, HypothesisLineage, IdentityAdjudication,
            IdentityAdjudicationId, IdentityOutcome, StatementVersion,
            StatementVersionId,
        )
        d = self.deps
        key = (str(signature.subject), signature.attribution)

        if decision.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED:
            # Parked: creates and revises no hypothesis, but is never discarded.
            self.adjudications.append(
                IdentityAdjudication(
                    id=IdentityAdjudicationId(d.ids.new_id("adj")),
                    subject_id=self.subject_id,
                    candidate_statement=proposal.statement,
                    candidate_signature=signature,
                    decision=decision,
                    created_at=self.now,
                    source_evidence_ids=(evidence.id,),
                    plausible_matches=decision.plausible_matches,
                    status=AdjudicationStatus.PARKED,
                    space_id=self.space_id,
                )
            )
            return

        if decision.outcome is IdentityOutcome.MATCH_EXISTING:
            hid = decision.matched_hypothesis_id
            if hid is None:
                return  # matched an in-flight lineage; evidence attaches below
            self._note_trajectory(hid, proposal)
            self._strengthen(evidence, hid)
            return

        # DISTINCT_NEW -- the durable id is issued HERE, after adjudication.
        hid = HypothesisId(d.ids.new_id("hyp"))
        self._note_trajectory(hid, proposal)
        self.lineages.append(
            HypothesisLineage(
                hypothesis_id=hid, subject_id=self.subject_id,
                space_id=self.space_id, signature_subject=signature.subject,
                attribution=signature.attribution, created_at=self.now,
            )
        )
        self.statement_versions.append(
            StatementVersion(
                id=StatementVersionId(d.ids.new_id("sv")), hypothesis_id=hid,
                statement=proposal.statement, claim_class=signature.claim_class,
                stance=signature.stance, temporal_scope=signature.temporal_scope,
                created_at_version=self.new_version_id,
            )
        )
        # R6: initial support comes from the existing application-owned
        # mechanism, applied to the triggering evidence. No separate constant.
        support = support_after_support(
            0.0, evidence.reliability.value, d.config.support_learning_rate
        )
        record = self._hyp_record(
            hypothesis_id=hid, statement=proposal.statement, support=support,
            supporting=(evidence.id,), contradicting=(), supersedes=None,
        )
        self.working[hid] = record
        # Appended, not assigned (M-2): two candidates in one plan may found
        # distinct lineages under the same bound, and the second must not erase
        # the first from the in-flight set the next candidate adjudicates
        # against.
        self.in_flight.setdefault(key, []).append(
            LineageView(
                hypothesis_id=hid, key=key, current_stance=signature.stance,
                in_flight=True, in_flight_statement=proposal.statement,
                in_flight_signature=signature,
            )
        )
        self.intents.append(
            _Intent(
                self._event(affected=hid, outcome=RevisionOutcome.HYPOTHESIZE,
                            evidence_id=evidence.id),
                record,
            )
        )
        self.edges.append(
            self._edge(evidence.id, hid, DependencyRelation.SUPPORTS)
        )

    def _note_trajectory(self, hid: HypothesisId, proposal) -> None:
        """Record an authored trajectory hint against a lineage (errata E-1).

        Plan-local and **content only**. It records a description for a
        prediction that may or may not form; it never confers support, never
        crosses ``prediction_support_threshold`` and never causes a prediction.
        ``_regenerate_predictions`` applies the gate first and consults these
        hints only for hypotheses that already passed it, so a hint attached to
        a sub-threshold lineage is simply never read.

        A parked (``AMBIGUOUS_REVIEW_REQUIRED``) candidate reaches neither call
        site: it creates no hypothesis, so it records no hint.
        """
        trajectory = getattr(proposal, "predicted_trajectory", None)
        if trajectory is not None:
            self.traj_hints.setdefault(hid, trajectory)

    def _strengthen(self, evidence: EvidenceRecord, hid: HypothesisId) -> None:
        """Attach supporting evidence to an existing lineage.

        One support event per (observation, lineage) regardless of path (F-3):
        a redundant SUPPORTS bearing coinciding with a MATCH_EXISTING attachment
        applies once and the duplicate is recorded, not applied twice.
        """
        prev = self.working.get(hid)
        if prev is None:
            return
        if evidence.id in prev.supporting_evidence_ids:
            return  # already applied for this (observation, lineage)
        new_support = support_after_support(
            prev.support.value, evidence.reliability.value,
            self.deps.config.support_learning_rate,
        )
        record = self._hyp_record(
            hypothesis_id=hid, statement=prev.statement, support=new_support,
            supporting=_dedup(prev.supporting_evidence_ids, (evidence.id,)),
            contradicting=prev.contradicting_evidence_ids,
            supersedes=prev.record_id,
        )
        self.working[hid] = record
        self.intents.append(
            _Intent(
                self._event(affected=hid, outcome=RevisionOutcome.STRENGTHEN,
                            evidence_id=evidence.id),
                record,
            )
        )
        self.edges.append(self._edge(evidence.id, hid, DependencyRelation.SUPPORTS))

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
            space_id=self.space_id,
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


@dataclass(frozen=True, slots=True)
class PlannedRevision:
    """The complete intended mutation for one interaction. Nothing is written.

    Built by :meth:`ModelRevisionEngine.plan` at sequence step 9, validated at
    step 13 and handed to :func:`commit_plan` at step 14. Derived state is
    deliberately absent: it is a computed projection, not a store write
    (§5.1, F-9).
    """

    subject_id: SubjectId
    space_id: SpaceId
    evidence: tuple[EvidenceRecord, ...]
    committed_events: tuple[RevisionEvent, ...]
    records: tuple[Hypothesis, ...]
    edges: tuple[DependencyEdge, ...]
    anomalies: tuple[AnomalyResolution, ...]
    lineages: tuple = ()
    statement_versions: tuple = ()
    adjudications: tuple = ()
    predictions: tuple[Prediction, ...] = ()
    inquiry: Inquiry | None = None
    provenance: ProvenanceRecord | None = None
    model: WorldModel | None = None
    current_pointer: CurrentModelSnapshot | None = None
    committed: bool = False
    result: ModelRevisionResult | None = None
    appraised: tuple = ()


def commit_plan(deps: ReasoningDependencies, plan: PlannedRevision) -> None:
    """**The sole writer** of governed reasoning state (§1.5, §3.1 step 14).

    No module other than this function may call a mutating method on a store in
    the reasoning bundle. It runs only inside an open ``UnitOfWork`` and only
    after complete-plan validation, so every write below is expected to succeed;
    a failure here is an internal invariant breach, not a model-behaviour
    outcome.

    Evidence is written **here**, with everything else -- not before appraisal.
    That is what closes the evidence-first partial mutation at the old
    ``core_loop.py:155-159``: a failed appraisal can no longer leave evidence
    persisted with no revision, because nothing is persisted until the whole
    plan is validated.
    """
    for record in plan.evidence:
        deps.evidence.add(record)
    for anomaly in plan.anomalies:
        deps.anomalies.add(anomaly)

    # M-3: durable reasoning state is written only for hypotheses that actually
    # committed.
    #
    # A lineage and its statement version are created provisionally at
    # DISTINCT_NEW, before the commit policy has ruled on the revision event
    # they belong to. If that event does not commit, the interaction holds: no
    # Hypothesis record, no ledger entry and no WorldModel version are written.
    # Writing the lineage anyway would leave a HypothesisLineage for a
    # hypothesis the model does not hold, and a StatementVersion whose
    # ``created_at_version`` names a WorldModel version that was never
    # appended -- orphan reasoning state, unreachable and unrevisable.
    #
    # The guard lives here, in the sole writer, rather than in the one plan
    # path that can currently produce the condition. That makes it an
    # invariant of the write boundary instead of a property of one caller, so
    # a future plan path cannot reintroduce the orphan by construction.
    #
    # This does NOT touch audit preservation. Evidence, anomaly resolutions and
    # parked identity adjudications are written above and below regardless of
    # whether the model committed: a rejected or held *interaction* is still
    # recorded, while rejected *reasoning state* is not (TD-18).
    committed_hypotheses = {record.hypothesis_id for record in plan.records}

    # Semantic-state stores are optional: a bundle that predates the boundary
    # (the SQLite adapter) simply has none, and a plan built against it carries
    # nothing for them.
    if deps.lineages is not None:
        for lineage in plan.lineages:
            if lineage.hypothesis_id in committed_hypotheses:
                deps.lineages.add(lineage)
    if deps.statement_versions is not None:
        for version in plan.statement_versions:
            if version.hypothesis_id in committed_hypotheses:
                deps.statement_versions.append(version)
    if deps.identity_adjudications is not None:
        for adjudication in plan.adjudications:
            deps.identity_adjudications.add(adjudication)
    for record in plan.records:
        deps.hypotheses.add(record)
    for event in plan.committed_events:
        deps.ledger.append(event)
    for edge in plan.edges:
        deps.dependencies.add_edge(edge)
    for prediction in plan.predictions:
        deps.predictions.add(prediction)
    if plan.inquiry is not None:
        deps.inquiries.add(plan.inquiry)
    # The model version, its pointer and the provenance record exist only when a
    # revision actually committed. On a hold ``plan.model`` is the *existing*
    # model, carried for reporting -- re-appending it would duplicate a version.
    if plan.committed:
        if plan.provenance is not None:
            deps.provenance.add(plan.provenance)
        if plan.model is not None:
            deps.world_models.append_version(plan.model)
        if plan.current_pointer is not None:
            deps.world_models.set_current_pointer(plan.current_pointer)


class ModelRevisionEngine:
    """Revises the persistent model in response to appraised evidence."""

    def __init__(self, deps: ReasoningDependencies) -> None:
        from sanuvia.application.reasoning.identity import DeterministicAdjudicator

        # Deterministic arm only. The R1 model-assisted resolver is Slice 2 and
        # is deliberately NOT wired: with none configured, a plausible-but-inexact
        # candidate parks rather than committing on an unmade judgement (§2 G).
        self._adjudicator = DeterministicAdjudicator(resolver=None)
        self._d = deps

    def _committed_views(self, subject_id, entering, space_id) -> dict:
        """Committed lineages, keyed by the immutable (subject, attribution).

        Each key maps to a **list**: the bound admits several lineages (M-2),
        and assigning rather than appending silently dropped every candidate
        but the last one retrieved.
        """
        from sanuvia.application.reasoning.identity import LineageView
        from sanuvia.domain import Stance

        d = self._d
        store = getattr(d, "lineages", None)
        versions = getattr(d, "statement_versions", None)
        if store is None:
            return {}
        views: dict = {}
        for lineage in store.list_for_subject(subject_id, space_id=space_id):
            history = tuple(versions.history(lineage.hypothesis_id)) if versions else ()
            current = history[-1].stance if history else Stance.OPEN
            views.setdefault(lineage.lineage_key, []).append(
                LineageView(
                    hypothesis_id=lineage.hypothesis_id, key=lineage.lineage_key,
                    current_stance=current, versions=history,
                )
            )
        return views

    def plan(
        self,
        subject_id: SubjectId,
        evidence_batch: tuple[EvidenceRecord, ...],
        current_model: WorldModel | None,
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> PlannedRevision:
        """Construct the complete revision plan. **Writes nothing** (step 9).

        Durable hypothesis ids are issued inside this call, but only after
        identity adjudication, and only into the plan -- never into a store.
        """
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
            space_id=space_id,
            working={
                h.hypothesis_id: h
                for h in d.hypotheses.list_for_subject(subject_id, space_id=space_id)
            },
        )
        entering = tuple(d.hypotheses.list_for_subject(subject_id, space_id=space_id))
        run.entering = entering
        run.adjudicator = self._adjudicator
        run.committed_views = self._committed_views(subject_id, entering, space_id)

        for evidence in evidence_batch:
            run.ingest(evidence)

        committed_intents = [
            i for i in run.intents if d.commit_policy.should_commit(i.event)
        ]
        if not committed_intents:
            # Nothing committed: the model holds (FR-MR-003). Evidence, anomaly
            # resolutions and any parked candidates still belong to the plan;
            # understanding is unchanged.
            return PlannedRevision(
                subject_id=subject_id, space_id=space_id,
                evidence=tuple(evidence_batch),
                committed_events=(), records=(), edges=(),
                anomalies=tuple(run.anomalies),
                lineages=tuple(run.lineages),
                statement_versions=tuple(run.statement_versions),
                adjudications=tuple(run.adjudications),
                appraised=tuple(run.appraised),
                result=ModelRevisionResult(
                    subject_id=subject_id, revision_events=(),
                    anomaly_resolutions=tuple(run.anomalies),
                    new_model_version_id=None, space_id=space_id,
                ),
                model=current_model, committed=False,
            )

        committed_events: list[RevisionEvent] = []
        records: list[Hypothesis] = []
        for intent in committed_intents:
            if intent.record is not None:
                records.append(intent.record)
            committed_events.append(intent.event.committed(run.new_version_id))

        # Prospective post-commit active set. Equivalent to re-reading the store
        # after the writes, because ``working`` holds the latest evaluation per
        # lineage in first-seen order -- the same contract list_for_subject has.
        active = list(run.working.values())
        supports = [h.support.value for h in active]
        model_uncertainty = aggregate_model_uncertainty(supports)

        predictions = self._regenerate_predictions(active, run)
        inquiry = self._maybe_open_inquiry(
            run, active, supports, model_uncertainty, committed_events, now
        )

        provenance = ProvenanceRecord(
            id=ProvenanceRecordId(d.ids.new_id("prov")),
            subject_id=subject_id,
            traces_to_evidence_ids=tuple(e.id for e in evidence_batch),
            traces_to_revision_ids=tuple(e.id for e in committed_events),
            created_at=now,
            space_id=space_id,
        )

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
            space_id=space_id,
        )
        pointer = CurrentModelSnapshot(
            subject_id=subject_id,
            model_version_id=run.new_version_id,
            committed_at=now,
            space_id=space_id,
        )

        return PlannedRevision(
            subject_id=subject_id, space_id=space_id,
            evidence=tuple(evidence_batch),
            committed_events=tuple(committed_events),
            records=tuple(records),
            edges=tuple(run.edges),
            anomalies=tuple(run.anomalies),
            lineages=tuple(run.lineages),
            statement_versions=tuple(run.statement_versions),
            adjudications=tuple(run.adjudications),
            appraised=tuple(run.appraised),
            predictions=predictions,
            inquiry=inquiry,
            provenance=provenance,
            model=model,
            current_pointer=pointer,
            committed=True,
            result=ModelRevisionResult(
                subject_id=subject_id,
                revision_events=tuple(committed_events),
                anomaly_resolutions=tuple(run.anomalies),
                new_model_version_id=run.new_version_id,
                space_id=space_id,
            ),
        )

    def _regenerate_predictions(
        self, active: list[Hypothesis], run: _RevisionRun
    ) -> tuple[Prediction, ...]:
        cfg = self._d.config
        # A trajectory kind, once established for a hypothesis, carries forward
        # across versions. (Full prediction lifecycle governance — creation,
        # expiry, confirmation — is spec-unresolved and kept minimal here.)
        prior_trajectory: dict[HypothesisId, FutureTrajectory] = {}
        for prior in self._d.predictions.list_for_subject(
            run.subject_id, space_id=run.space_id
        ):
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
                subject_id=run.subject_id,
                trajectory=trajectory,
                likelihood=PredictionLikelihood(h.support.value),
                derived_from_hypothesis_ids=(h.hypothesis_id,),
                derived_from_evidence_ids=h.supporting_evidence_ids,
                model_version_id=run.new_version_id,
                created_at=run.now,
                space_id=run.space_id,
            )
            predictions.append(prediction)
            # Mutation-free: the edge joins the plan and commit_plan writes it.
            run.edges.append(
                run._edge(prediction.id, h.hypothesis_id,
                          DependencyRelation.DERIVED_FROM)
            )
        return tuple(predictions)

    def _maybe_open_inquiry(
        self,
        run: _RevisionRun,
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
            subject_id=run.subject_id,
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
            space_id=run.space_id,
        )
        return inquiry
