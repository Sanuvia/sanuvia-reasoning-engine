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
    AcquisitionStrategy,
    CognitiveState,
    EvidenceRecord,
    Hypothesis,
    Inquiry,
    ModelRevisionResult,
    Prediction,
    RecognitionEvent,
    RevisionLedgerEntry,
    SubjectId,
    WorldModel,
    WorldModelVersionId,
)

from .dependencies import ReasoningDependencies
from .model_revision import ModelRevisionEngine
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
        self, subject_id: SubjectId, evidence_batch: Sequence[EvidenceRecord]
    ) -> InteractionResult:
        d = self._d
        batch = tuple(evidence_batch)

        # Mark the ledger position so we can report revisions from *this*
        # interaction only.
        prior = d.ledger.read(subject_id)
        prior_seq = prior[-1].sequence_no if prior else -1

        # 1. get_current_model (the model state entering this interaction)
        current = d.world_models.get_current_model(subject_id)
        version_before = None if current is None else current.model_version_id
        uncertainty_before = (
            None if current is None else current.model_uncertainty.value
        )

        # 2. identify_competing_hypotheses / 3. rank_by_uncertainty
        competing = self._rank_by_uncertainty(
            d.hypotheses.list_for_subject(subject_id)
        )
        # 4. compute_expected_information_gain
        eig = expected_information_gain([h.support.value for h in competing])

        # 5. get_user_cognitive_state / 6. select_acquisition_strategy
        cognitive = d.cognitive_state.current_state(subject_id)
        strategy = select_acquisition_strategy(cognitive)

        # 7. acquire_evidence (Phase 0: record the supplied batch)
        for evidence in batch:
            d.evidence.add(evidence)

        # 8. revise_model -> ModelRevisionResult
        applied = self._engine.revise(subject_id, batch, current)

        since = tuple(d.ledger.read_since(subject_id, prior_seq))
        return InteractionResult(
            subject_id=subject_id,
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
            active_hypotheses=tuple(d.hypotheses.list_for_subject(subject_id)),
            predictions=applied.predictions,
            inquiry=applied.inquiry,
            recognition_events=tuple(d.recognition.list_for_subject(subject_id)),
            revision_events_since_prior=since,
        )

    @staticmethod
    def _rank_by_uncertainty(
        hypotheses: Sequence[Hypothesis],
    ) -> tuple[Hypothesis, ...]:
        """Rank competing hypotheses, strongest support first — the live
        contenders whose competition drives model uncertainty (FR-IQ-005)."""
        return tuple(sorted(hypotheses, key=lambda h: h.support.value, reverse=True))
