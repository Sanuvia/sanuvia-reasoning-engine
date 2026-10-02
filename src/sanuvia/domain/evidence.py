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
    ParticipantId,
    SpaceId,
    SubjectId,
)
from .scope import DEFAULT_SPACE_ID
from .uncertainty import (
    ClassificationConfidence,
    EvidenceReliability,
    ProvenanceConfidence,
)


@dataclass(frozen=True, slots=True)
class SourceObservationRef:
    """Where an admitted observation came from (Technical Design v1.5.4 §2 A).

    The within-interaction ``observation_index`` is the part Run 002 lost: two
    observations extracted from the same interaction were indistinguishable.
    The mapping to the canonical :data:`EvidenceRecordId` is one-to-one within an
    execution and must be resolvable in both directions.
    """

    transcript_id: str
    interaction_index: int
    observation_index: int

    def __post_init__(self) -> None:
        if not self.transcript_id:
            raise InvariantViolation("SourceObservationRef.transcript_id must be non-empty")
        if self.interaction_index < 0:
            raise InvariantViolation("SourceObservationRef.interaction_index must be >= 0")
        if self.observation_index < 0:
            raise InvariantViolation("SourceObservationRef.observation_index must be >= 0")


class EvidenceRole(Enum):
    """What an admitted observation *is* (Technical Design v1.5.4 §2 E).

    ``absence`` is deliberately **not** a member: it is an extraction outcome
    that yields zero admitted records and executes the empty-evidence hold, not
    a role an EvidenceRecord can carry (locked §3.2).
    """

    EVENT_OBSERVATION = "event_observation"
    ACCOUNT = "account"
    RESPONSE_OR_RESONANCE = "response_or_resonance"
    META_INSTRUCTION = "meta_instruction"


#: Roles that are sent to the EvidenceAppraiser (governance ruling Q1). A record
#: whose role is absent from this set is admitted and preserved with its standing
#: and provenance, but receives **no appraisal call** and can therefore trigger no
#: bearing, proposal, divergence, identity adjudication or support change.
APPRAISABLE_ROLES: frozenset[EvidenceRole] = frozenset(
    {EvidenceRole.EVENT_OBSERVATION, EvidenceRole.ACCOUNT}
)


class EvidenceSourceKind(Enum):
    """Whose account or surface the observation *is* (§2 E)."""

    PARTICIPANT = "participant"
    SANUVIA = "sanuvia"
    SYSTEM_SURFACE = "system_surface"
    EXTERNAL_SOURCE = "external_source"


class EvidenceSubjectKind(Enum):
    """What the observation is *about* (§2 E)."""

    PARTICIPANT = "participant"
    DYAD = "dyad"
    THIRD_PARTY = "third_party"
    NONE = "none"


@dataclass(frozen=True, slots=True)
class EvidenceStanding:
    """The three governed semantic properties of an admitted observation (§2 E).

    Deliberately distinct from four things it must never be collapsed into:

    * :attr:`Provenance.source` — free-text capture mechanism/location.
    * :attr:`EvidenceRecord.actor_id` — who handed the observation to the system.
    * :attr:`EvidenceRecord.subject_id` — the modelled subject / isolation key.
    * the role — which is *what the observation is*, not who it came from.
    """

    source_kind: EvidenceSourceKind
    subject_kind: EvidenceSubjectKind
    role: EvidenceRole
    source_id: ParticipantId | None = None
    subject_id: ParticipantId | None = None

    def __post_init__(self) -> None:
        if self.source_kind is EvidenceSourceKind.PARTICIPANT and not self.source_id:
            raise InvariantViolation(
                "EvidenceStanding.source_id is required when source_kind is PARTICIPANT"
            )
        if (
            self.subject_kind
            in (EvidenceSubjectKind.PARTICIPANT, EvidenceSubjectKind.THIRD_PARTY)
            and not self.subject_id
        ):
            raise InvariantViolation(
                "EvidenceStanding.subject_id is required when subject_kind is "
                "PARTICIPANT or THIRD_PARTY"
            )

    @property
    def is_appraisable(self) -> bool:
        """Whether this record is sent to the appraiser (ruling Q1)."""
        return self.role in APPRAISABLE_ROLES

    @property
    def is_participant_account(self) -> bool:
        """The three-part test §2 J.1 rules 2-3 apply to a divergence endpoint."""
        return (
            self.role is EvidenceRole.ACCOUNT
            and self.source_kind is EvidenceSourceKind.PARTICIPANT
            and self.source_id is not None
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
    # Where the observation came from (§2 A). Optional so Phase 0 callers that
    # predate the semantic-state boundary keep working; the Phase 1 pipeline
    # always supplies it, and check 7 requires it to resolve both ways.
    source_ref: SourceObservationRef | None = None
    # The three governed semantic properties (§2 E). Optional for the same
    # reason; admission assigns it on the Phase 1 path.
    standing: EvidenceStanding | None = None

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
