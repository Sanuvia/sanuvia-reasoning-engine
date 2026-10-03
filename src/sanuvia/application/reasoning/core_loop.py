"""The Core Loop.

Implements the reasoning cycle end to end, in the order the spec fixes:

    get_current_model
      -> identify_competing_hypotheses
      -> rank_by_uncertainty
      -> compute_expected_information_gain
      -> get_user_cognitive_state
      -> select_acquisition_strategy
      -> acquire_evidence
      -> revise_model
      -> ModelRevisionResult

In Phase 0 evidence is *supplied* (synthetic, scripted) rather than actively
solicited, so ``acquire_evidence`` records the provided batch. The
identify/rank/EIG steps are still computed and exposed — they are the engine's
reasoning about what it would want to resolve — even though they do not gate the
injected evidence in this phase.

The loop returns an :class:`InteractionResult` bundling exactly the
"required outputs at each step" the Evaluation Protocol asks for, so Phase 1's
demonstrator can render them directly.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sanuvia.domain import (
    DEFAULT_SPACE_ID,
    AcquisitionStrategy,
    CognitiveState,
    EvidenceRecord,
    Hypothesis,
    Inquiry,
    InvariantViolation,
    ModelRevisionResult,
    Prediction,
    RecognitionEvent,
    RevisionLedgerEntry,
    SpaceId,
    SubjectId,
    WorldModel,
    WorldModelVersionId,
)

from .dependencies import ReasoningDependencies
from .plan_validation import RevisionPlan, validate_plan
from .model_revision import ModelRevisionEngine, PlannedRevision, RevisionApplied, commit_plan
from .scoring import expected_information_gain


def select_acquisition_strategy(state: CognitiveState) -> AcquisitionStrategy:
    """Map cognitive state to an acquisition strategy (FR-IQ-006).

    Cognitive state is a *feasibility gate*: it constrains the form/intensity of
    acquisition, it does not replace uncertainty-driven prioritisation. Under
    reduced capacity or distress the engine favours minimal/passive acquisition.
    """
    return {
        CognitiveState.DISTRESSED: AcquisitionStrategy.PASSIVE,
        CognitiveState.REDUCED_CAPACITY: AcquisitionStrategy.MINIMAL,
        CognitiveState.UNKNOWN: AcquisitionStrategy.MINIMAL,
        CognitiveState.NEUTRAL: AcquisitionStrategy.ACTIVE,
        CognitiveState.ENGAGED: AcquisitionStrategy.TARGETED,
    }[state]


@dataclass(frozen=True)
class InteractionResult:
    """Everything observable after one interaction — the Evaluation Protocol's
    'required outputs at each step'."""

    subject_id: SubjectId
    space_id: SpaceId
    model: WorldModel | None
    committed: bool
    # the evidence the engine actually ingested this interaction
    ingested_evidence: tuple[EvidenceRecord, ...]
    # the model state entering the interaction (before revision)
    model_version_before: WorldModelVersionId | None
    model_uncertainty_before: float | None
    # what the engine was reasoning about before revising
    competing_hypotheses_before: tuple[Hypothesis, ...]
    expected_information_gain_before: float
    cognitive_state: CognitiveState
    acquisition_strategy: AcquisitionStrategy
    # what the revision produced
    revision_result: ModelRevisionResult
    active_hypotheses: tuple[Hypothesis, ...]
    predictions: tuple[Prediction, ...]
    inquiry: Inquiry | None
    recognition_events: tuple[RecognitionEvent, ...]
    revision_events_since_prior: tuple[RevisionLedgerEntry, ...]

    @property
    def model_uncertainty(self) -> float | None:
        return None if self.model is None else self.model.model_uncertainty.value


class CoreLoop:
    """Drives one reasoning interaction over a batch of evidence."""

    def __init__(self, deps: ReasoningDependencies) -> None:
        self._d = deps
        self._engine = ModelRevisionEngine(deps)

    def ingest(
        self,
        subject_id: SubjectId,
        evidence_batch: Sequence[EvidenceRecord],
        *,
        space_id: SpaceId = DEFAULT_SPACE_ID,
    ) -> InteractionResult:
        d = self._d
        batch = tuple(evidence_batch)

        # Ownership gate (Finding 1): every evidence record must belong to the
        # interaction's (space, subject). Reject a batch that tries to smuggle in
        # evidence owned by another subject or another space.
        for evidence in batch:
            if evidence.subject_id != subject_id or evidence.space_id != space_id:
                raise InvariantViolation(
                    "Evidence ownership does not match the interaction scope: "
                    f"evidence {evidence.id} is owned by "
                    f"(space={evidence.space_id}, subject={evidence.subject_id}) "
                    f"but the interaction is (space={space_id}, subject={subject_id})"
                )

        # Mark the ledger position so we can report revisions from *this*
        # interaction only.
        prior = d.ledger.read(subject_id, space_id=space_id)
        prior_seq = prior[-1].sequence_no if prior else -1

        # 1. get_current_model (the model state entering this interaction)
        current = d.world_models.get_current_model(subject_id, space_id=space_id)
        version_before = None if current is None else current.model_version_id
        uncertainty_before = (
            None if current is None else current.model_uncertainty.value
        )

        # 2. identify_competing_hypotheses / 3. rank_by_uncertainty
        competing = self._rank_by_uncertainty(
            d.hypotheses.list_for_subject(subject_id, space_id=space_id)
        )
        # 4. compute_expected_information_gain
        eig = expected_information_gain([h.support.value for h in competing])

        # 5. get_user_cognitive_state / 6. select_acquisition_strategy
        cognitive = d.cognitive_state.current_state(subject_id)
        strategy = select_acquisition_strategy(cognitive)

        # 7. acquire_evidence -- NOT a write.
        #
        # Technical Design v1.5.4 §3.4. The old code added every record to the
        # evidence store here, BEFORE appraisal, so a failed appraisal left
        # evidence persisted with no revision -- partial in-memory mutation that
        # serialisation masked but did not prevent. Evidence admission is now
        # part of the plan, not a precondition of it: the batch is handed to the
        # planner and written by ``commit_plan`` with everything else, or not at
        # all.

        # 8. plan (pure) -> validate the COMPLETE plan -> commit atomically.
        planned = self._engine.plan(subject_id, batch, current, space_id=space_id)
        self._validate(planned, subject_id, space_id)
        commit_plan(d, planned)
        applied = RevisionApplied(
            model=planned.model,
            result=planned.result,
            predictions=planned.predictions,
            inquiry=planned.inquiry,
            committed=planned.committed,
        )

        since = tuple(d.ledger.read_since(subject_id, prior_seq, space_id=space_id))
        return InteractionResult(
            subject_id=subject_id,
            space_id=space_id,
            model=applied.model,
            committed=applied.committed,
            ingested_evidence=batch,
            model_version_before=version_before,
            model_uncertainty_before=uncertainty_before,
            competing_hypotheses_before=competing,
            expected_information_gain_before=eig,
            cognitive_state=cognitive,
            acquisition_strategy=strategy,
            revision_result=applied.result,
            active_hypotheses=tuple(
                d.hypotheses.list_for_subject(subject_id, space_id=space_id)
            ),
            predictions=applied.predictions,
            inquiry=applied.inquiry,
            recognition_events=tuple(
                d.recognition.list_for_subject(subject_id, space_id=space_id)
            ),
            revision_events_since_prior=since,
        )

    @staticmethod
    def _rank_by_uncertainty(
        hypotheses: Sequence[Hypothesis],
    ) -> tuple[Hypothesis, ...]:
        """Rank competing hypotheses, strongest support first — the live
        contenders whose competition drives model uncertainty (FR-IQ-005)."""
        return tuple(sorted(hypotheses, key=lambda h: h.support.value, reverse=True))


    def _validate(self, planned, subject_id, space_id) -> None:
        """Complete-plan validation before any mutation (§3.1 step 13, §3.2).

        Mutation-free. Raises ``GovernedRejection`` on the first failure, which
        the caller's UnitOfWork turns into a restore plus a rejected-plan audit
        record -- nothing reaches a store.
        """
        d = self._d
        committed = {
            r.id: r for r in d.evidence.list_for_subject(subject_id, space_id=space_id)
        }
        active = {
            h.hypothesis_id: h
            for h in d.hypotheses.list_for_subject(subject_id, space_id=space_id)
        }
        lineage_keys: dict = {}
        stances: dict = {}
        store = getattr(d, "lineages", None)
        versions = getattr(d, "statement_versions", None)
        if store is not None:
            from sanuvia.domain import Stance

            for lineage in store.list_for_subject(subject_id, space_id=space_id):
                lineage_keys[lineage.lineage_key] = lineage.hypothesis_id
                history = (
                    tuple(versions.history(lineage.hypothesis_id)) if versions else ()
                )
                stances[lineage.hypothesis_id] = (
                    history[-1].stance if history else Stance.OPEN
                )
        plan = RevisionPlan(
            subject_id=subject_id,
            space_id=space_id,
            admitted=tuple(planned.evidence),
            appraised=tuple(planned.appraised),
            edges=tuple(planned.edges),
            intended_evidence_ids=tuple(r.id for r in planned.evidence),
        )
        validate_plan(
            plan,
            committed_evidence=committed,
            active_hypotheses=active,
            lineage_stance=stances,
            lineage_key_index=lineage_keys,
        )
