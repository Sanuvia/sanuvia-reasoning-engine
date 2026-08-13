"""Prediction / FutureTrajectory (FR-RS-004/005).

A Prediction is a *testable, assessable consequence* of the current
understanding — anticipation ("given the model, what becomes likely?"), not
forecasting and not advice. Epistemic boundary: a Prediction is **not** a
Recommendation and does not determine an intervention. No Recommendation object
exists in the frozen spec; reasoning terminates at Inquiry, never at advice.

Hard product constraint — *no relationship-failure predictions, ever*
(Programme Part 2; FR-RF-002). Rather than rely on a downstream filter alone,
the permitted trajectory kinds below simply **cannot express failure**: the type
makes the illegal output unrepresentable.

Traceability. A Prediction is derived from, and traceable to, *the hypotheses
(plural) and evidence* that generated it (FR-RS-004). OPEN (spec-unresolved):
whether a Prediction may arise from the WorldModel without any hypothesis is not
confirmed either way, so ``derived_from_hypothesis_ids`` may be empty; but a
Prediction with neither hypotheses nor evidence has nothing to be traceable to
and is rejected.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .errors import InvariantViolation
from .identifiers import (
    EvidenceRecordId,
    HypothesisId,
    PredictionId,
    SpaceId,
    SubjectId,
    WorldModelVersionId,
)
from .scope import DEFAULT_SPACE_ID
from .uncertainty import PredictionLikelihood


class TrajectoryKind(Enum):
    """The only permitted shapes of a future trajectory.

    Deliberately mirrors the Blueprint's permitted outputs (observed
    trajectories, recurring cycles, frequency changes, interruption
    opportunities). There is intentionally **no** ``FAILURE`` member — a
    relationship-failure prediction is structurally impossible to construct.
    """

    OBSERVED_TRAJECTORY = "observed_trajectory"
    RECURRING_CYCLE = "recurring_cycle"
    FREQUENCY_CHANGE = "frequency_change"
    INTERRUPTION_OPPORTUNITY = "interruption_opportunity"


@dataclass(frozen=True, slots=True)
class FutureTrajectory:
    """A projected trajectory: what the current model suggests may unfold. It
    describes a pattern's direction, never a verdict on the relationship."""

    kind: TrajectoryKind
    description: str

    def __post_init__(self) -> None:
        if not self.description:
            raise InvariantViolation("FutureTrajectory.description must be non-empty")


@dataclass(frozen=True, slots=True)
class Prediction:
    """An immutable, traceable prediction with an attached likelihood.

    ``likelihood`` is a mandatory attached uncertainty, never omitted for being
    low (FR-RS-005).
    """

    id: PredictionId
    # Who this prediction concerns (Finding 1). Owned by exactly one subject so
    # a prediction can never be returned for another subject.
    subject_id: SubjectId
    trajectory: FutureTrajectory
    likelihood: PredictionLikelihood
    derived_from_hypothesis_ids: tuple[HypothesisId, ...]
    derived_from_evidence_ids: tuple[EvidenceRecordId, ...]
    model_version_id: WorldModelVersionId
    created_at: datetime
    # Isolation boundary this prediction belongs to (Finding 1).
    space_id: SpaceId = DEFAULT_SPACE_ID

    def __post_init__(self) -> None:
        if not (self.derived_from_hypothesis_ids or self.derived_from_evidence_ids):
            raise InvariantViolation(
                "A Prediction must be traceable to at least one hypothesis or "
                "evidence record (FR-RS-004)"
            )
        if not self.space_id:
            raise InvariantViolation("Prediction.space_id must be non-empty")
