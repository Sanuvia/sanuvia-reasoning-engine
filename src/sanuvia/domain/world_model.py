"""Persistent Understanding (FR-PU-001 .. FR-PU-005).

The WorldModel is the living representation of the engine's current
understanding of one reasoning participant's emotional and relational world. It
represents *relationships*, not a psychological profile of an isolated
individual.

Versioned and append-only. A WorldModel version is **immutable once written**. A
revision produces a **new** version (a new ``model_version_id``) rather than
mutating the old one, so history is never destroyed (FR-PU-003). The
``CurrentModelSnapshot`` is a lightweight pointer to the latest *committed*
version — not a separate parallel copy of the content.

Uncertainty is intrinsic. Every version carries an aggregate ``ModelUncertainty``
(FR-PU-002/004). It must be able to increase, not merely decrease.

OPEN (spec-unresolved — represented, not decided):
* Whether ``provenance`` (the field) *contains* or merely *references* a
  ``ProvenanceRecord`` is not resolved; both are modelled so either is possible.
* Whether ``SystemModellingContext`` is a stored object or a retrieval-time
  parameter is unresolved (FR-PU-005); it is modelled as a value that can be
  either persisted or passed in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .errors import InvariantViolation
from .identifiers import (
    EvidenceRecordId,
    HypothesisId,
    InquiryId,
    PredictionId,
    ProvenanceRecordId,
    ReasoningSystemId,
    RevisionEventId,
    SubjectId,
    SystemModellingContextId,
    WorldModelVersionId,
)
from .uncertainty import ModelUncertainty


@dataclass(frozen=True, slots=True)
class ProvenanceRecord:
    """A first-class provenance object, cited independently alongside a
    WorldModel (FR-PU-004).

    It traces a model version's content back to the evidence and revision events
    that justify it. Distinct from an EvidenceRecord's inline ``Provenance``
    value: this concerns the *model's* lineage, not a single observation's origin.
    """

    id: ProvenanceRecordId
    subject_id: SubjectId
    traces_to_evidence_ids: tuple[EvidenceRecordId, ...]
    traces_to_revision_ids: tuple[RevisionEventId, ...]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SystemModellingContext:
    """Contextual parameters that scope how a model is built/retrieved
    (FR-PU-005).

    Its ownership — stored object vs. retrieval-time parameter — is unresolved.
    Modelled as an immutable value with an optional id so it can be persisted
    *or* passed transiently without committing to either.
    """

    parameters: tuple[tuple[str, str], ...] = ()
    id: SystemModellingContextId | None = None


@dataclass(frozen=True, slots=True)
class WorldModel:
    """An immutable, versioned snapshot of understanding for one subject.

    Addressed uniquely by ``(model_version_id, subject_id)`` (FR-PU-001). Holds
    the ids of the reasoning objects that make up this version's understanding —
    the active hypotheses, predictions, and inquiries — plus the aggregate model
    uncertainty and a reference to the provenance for this version.

    The content sets are id references, not embedded objects: each of those
    objects is separately owned and independently versioned. A WorldModel version
    is a coherent *snapshot* over them at a point in the revision history.
    """

    model_version_id: WorldModelVersionId
    subject_id: SubjectId
    reasoning_system_id: ReasoningSystemId
    model_uncertainty: ModelUncertainty
    active_hypothesis_ids: tuple[HypothesisId, ...]
    active_prediction_ids: tuple[PredictionId, ...]
    active_inquiry_ids: tuple[InquiryId, ...]
    created_at: datetime
    # The revision event whose commit produced this version. None only for the
    # genesis (empty) model of a subject.
    created_by_revision_id: RevisionEventId | None = None
    provenance_record_id: ProvenanceRecordId | None = None
    system_modelling_context: SystemModellingContext | None = None


@dataclass(frozen=True, slots=True)
class CurrentModelSnapshot:
    """A pointer to the latest *committed* WorldModel version for a subject
    (FR-PU-003).

    This is not a second copy of the model — it identifies which immutable
    version is current. ``get_current_model`` resolves this to the WorldModel via
    the repository.
    """

    subject_id: SubjectId
    model_version_id: WorldModelVersionId
    committed_at: datetime

    def __post_init__(self) -> None:
        if not self.model_version_id:
            raise InvariantViolation(
                "CurrentModelSnapshot must point at a committed model version"
            )
