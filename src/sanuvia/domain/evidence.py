"""Evidence Management domain objects (FR-EM-001 .. FR-EM-005).

The Evidence/Inference split is the structural spine that separates Sanuvia from
an LLM wrapper: the system must never treat its own conclusions as fresh proof.
``EvidenceRecord`` and ``InferenceRecord`` are therefore **distinct types with no
inheritance relationship** — a value of one can never be passed where the other
is expected, and an inference can never be re-ingested as evidence (FR-EM-005).

Both are immutable (FR-EM-001). Correction is never in-place: an EvidenceRecord
is *superseded*, and the supersession is expressed through revision history, not
by mutating the record (FR-EM-003). See ``dependency.py`` /
``application.ports`` for how supersession is recorded on the RevisionLedger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .errors import InvariantViolation
from .identifiers import (
    ActorId,
    EvidenceRecordId,
    InferenceRecordId,
    ObjectRef,
    SpaceId,
    SubjectId,
)
from .scope import DEFAULT_SPACE_ID
from .uncertainty import (
    ClassificationConfidence,
    EvidenceReliability,
    ProvenanceConfidence,
)


class EvidenceClass(Enum):
    """The six evidence classes (FR-EM-004).

    ``FAILED_ACQUISITION`` is a first-class, evidence-producing outcome — a
    failed or off-target acquisition is *not* the absence of evidence and must
    not be discarded. It must lead to competing candidate explanations rather
    than a single default conclusion (handled downstream in the reasoning
    increment; the class exists here so the outcome is representable).
    """

    NARRATIVE = "narrative"
    REFLECTIVE = "reflective"
    BEHAVIOURAL = "behavioural"
    CONTRADICTORY = "contradictory"
    MISSING = "missing"
    FAILED_ACQUISITION = "failed_acquisition"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where and how a piece of evidence was captured (FR-EM-002).

    ``source`` and ``acquisition_metadata`` must be *sufficient to identify the
    origin*. ``confidence`` expresses how much that recorded origin can itself be
    trusted. Provenance is a property carried *by* an EvidenceRecord, not an
    independently owned object.
    """

    source: str
    confidence: ProvenanceConfidence
    acquisition_metadata: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.source:
            raise InvariantViolation("Provenance.source must be non-empty (FR-EM-002)")


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """An immutable item of accepted evidence (FR-EM-001).

    Evidence is information that *contributes to* understanding — it is never
    assumed to be objective truth. It carries its classification, its origin
    (provenance), and two typed uncertainties: how reliable the observation is
    (``reliability``) and how confident we are in its classification
    (``classification_confidence``, FR-EM-004).

    ``content`` is the captured observation itself. This type deliberately holds
    *no* interpretation field — interpretation becomes a Hypothesis, never a
    property of the evidence.
    """

    id: EvidenceRecordId
    subject_id: SubjectId
    evidence_class: EvidenceClass
    content: str
    provenance: Provenance
    reliability: EvidenceReliability
    classification_confidence: ClassificationConfidence
    occurred_at: datetime
    # Optional link to the interaction/acquisition that produced this record.
    origin_ref: ObjectRef | None = None
    # Isolation boundary this evidence belongs to (Finding 1). Defaulted for
    # single-space callers; the service assigns it from the interaction scope.
    space_id: SpaceId = DEFAULT_SPACE_ID
    # Who contributed this observation (a.k.a. member id) — contribution
    # provenance, distinct from the subject the evidence concerns.
    actor_id: ActorId | None = None

    def __post_init__(self) -> None:
        if not self.content:
            raise InvariantViolation("EvidenceRecord.content must be non-empty")
        if not self.space_id:
            raise InvariantViolation("EvidenceRecord.space_id must be non-empty")


@dataclass(frozen=True, slots=True)
class InferenceRecord:
    """A system-derived inference — **not** an observation (FR-EM-005).

    An InferenceRecord is what the engine *concluded*, derived from evidence
    and/or other inferences. It is a distinct object type from EvidenceRecord and
    must never be persisted or presented as one. There is intentionally no
    conversion path from InferenceRecord to EvidenceRecord.

    The exact relationship of an InferenceRecord to Hypothesis/Prediction is
    left **unresolved** by the frozen spec; ``relates_to`` is therefore an
    open-ended, optional set of references rather than a committed linkage.
    """

    id: InferenceRecordId
    subject_id: SubjectId
    content: str
    derived_from_evidence_ids: tuple[EvidenceRecordId, ...]
    derived_from_inference_ids: tuple[InferenceRecordId, ...]
    produced_at: datetime
    # OPEN (spec-unresolved): how an inference attaches to Hypothesis/Prediction/
    # WorldModel is not specified. Kept deliberately loose; do not assume a shape.
    relates_to: tuple[ObjectRef, ...] = field(default=())
    # Isolation boundary this inference belongs to (Finding 1).
    space_id: SpaceId = DEFAULT_SPACE_ID

    def __post_init__(self) -> None:
        if not self.content:
            raise InvariantViolation("InferenceRecord.content must be non-empty")
