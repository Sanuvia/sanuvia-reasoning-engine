"""Reflection / Recognition (FR-RF-001/002/004) — data model only.

A ``RecognitionEvent`` represents a *Recognition Condition*: an evidence-grounded
recurring pattern that has become coherent enough that it *could* be surfaced to
the participant. In Phase 0 this is a **data model only**.

Two things are explicitly out of scope here:

* ``detect_recognition_condition`` — the computation that decides *when* a
  Recognition Condition exists — is interface-only and deferred (see the
  application ports). It is not implemented, and must not be faked.
* *Surfacing* a recognition to a human is a separate concern owned by
  Interaction & Intervention (FR-RF-003) at Phase 2. Representing a recognition
  is not the same as surfacing it. Nothing here is user-facing.

Epistemic restriction (FR-RF-002): a recognition may describe trajectories,
cycles, frequency changes, or interruption opportunities — and must **never**
predict relationship failure. As with Prediction, the permitted kinds simply
cannot express failure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .errors import InvariantViolation
from .identifiers import (
    EvidenceRecordId,
    RecognitionEventId,
    SpaceId,
    SubjectId,
    WorldModelVersionId,
)
from .scope import DEFAULT_SPACE_ID


class RecognitionKind(Enum):
    """Permitted recognition kinds (FR-RF-002). No ``FAILURE`` member exists."""

    RECURRING_CYCLE = "recurring_cycle"
    FREQUENCY_CHANGE = "frequency_change"
    OBSERVED_TRAJECTORY = "observed_trajectory"
    INTERRUPTION_OPPORTUNITY = "interruption_opportunity"


@dataclass(frozen=True, slots=True)
class RecognitionEvent:
    """An immutable, provenance-bound Recognition Condition record.

    Must remain traceable to the evidence and model state it was represented from
    (FR-RF-004); it therefore cites both its supporting evidence and the model
    version it was drawn from.
    """

    id: RecognitionEventId
    subject_id: SubjectId
    kind: RecognitionKind
    description: str
    supporting_evidence_ids: tuple[EvidenceRecordId, ...]
    model_version_id: WorldModelVersionId
    created_at: datetime
    # Isolation boundary this recognition belongs to (Finding 1).
    space_id: SpaceId = DEFAULT_SPACE_ID

    def __post_init__(self) -> None:
        if not self.description:
            raise InvariantViolation("RecognitionEvent.description must be non-empty")
        if not self.supporting_evidence_ids:
            raise InvariantViolation(
                "A RecognitionEvent must be provenance-bound to supporting "
                "evidence (FR-RF-004)"
            )
