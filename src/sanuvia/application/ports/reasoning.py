"""Reasoning ports — seams for decisions the frozen spec assigns elsewhere or
leaves unresolved.

Keeping these behind interfaces is what lets the reasoning engine be *genuine*
without *faking* deferred logic:

* ``EvidenceAppraiser`` — the language-understanding boundary. Deciding which
  hypotheses a piece of evidence supports or contradicts, and proposing new
  candidate explanations, is the *foundation model's* responsibility per the
  architecture ("FM generates candidate inferences; Sanuvia manages hypotheses
  and revises models"). Phase 0 supplies a deterministic, scripted adapter; a
  later phase plugs an LLM in behind the same port. Hypothesis *identity/creation*
  is spec-unresolved, so the appraiser supplies the ``hypothesis_id`` — the engine
  does not invent one.

* ``CognitiveStateProvider`` — ``get_user_cognitive_state`` (FR-IQ-006). A single
  enum in Phase 0 (multi-dimensional CognitiveState is an explicit non-goal).

* ``RevisionCommitPolicy`` — the ``proposed -> committed`` transition governance
  (FR-MR-003) that the frozen spec explicitly does not resolve. The engine
  *asks* this policy; it does not embed a governance rule. The Phase-0 adapter is
  a loudly-labelled placeholder, not the real governance.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import NewType, Protocol, runtime_checkable

from sanuvia.domain import (
    ClaimClass,
    CognitiveState,
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceRole,
    EvidenceSourceKind,
    EvidenceSubjectKind,
    FutureTrajectory,
    Hypothesis,
    HypothesisId,
    RevisionEvent,
    SpaceId,
    Stance,
    SubjectId,
)

# Request-scoped handle types (Technical Design v1.5.4 §2 B). They are plain
# strings at runtime; the branding exists so a durable id can never be passed
# where a handle is expected without an explicit cast.
EvidenceHandle = NewType("EvidenceHandle", str)
HypothesisHandle = NewType("HypothesisHandle", str)
ParticipantLabel = NewType("ParticipantLabel", str)


@dataclass(frozen=True, slots=True)
class ProposedHypothesis:
    """A candidate explanation proposed from evidence.

    ``hypothesis_id`` is the lineage identity. Because how hypothesis identity is
    computed is unresolved by the frozen spec, the appraiser supplies it rather
    than the engine deriving one. ``predicted_trajectory`` optionally carries a
    language-understanding hint the engine may turn into a Prediction.
    """

    hypothesis_id: HypothesisId
    statement: str
    initial_support: float
    supporting_evidence_ids: tuple[EvidenceRecordId, ...]
    predicted_trajectory: FutureTrajectory | None = None


@dataclass(frozen=True, slots=True)
class Appraisal:
    """The appraisal of a single evidence record against current understanding.

    ``supports`` / ``contradicts`` reference existing hypotheses by lineage id;
    ``proposals`` are new candidate explanations. All three may be empty (e.g. a
    failed acquisition that yields only competing proposals, or evidence that is
    merely noted)."""

    supports: tuple[HypothesisId, ...] = ()
    contradicts: tuple[HypothesisId, ...] = ()
    proposals: tuple[ProposedHypothesis, ...] = field(default=())


# --- Semantic-state appraiser boundary (Technical Design v1.5.4 §2 C) --------
#
# The model proposes; the application/domain layer decides. Everything the model
# sees is request-scoped and opaque: no canonical EvidenceRecordId, no durable
# HypothesisId, no ParticipantId. The port change is what actually closes locked
# §3.1's prohibition on exposing durable identity as model-facing fields.


@dataclass(frozen=True, slots=True)
class EvidenceStandingView:
    """Presentation projection of ``EvidenceStanding`` (§2 C, D-01).

    Participants appear as request-scoped labels, never as ``ParticipantId``.
    """

    role: EvidenceRole
    source_kind: EvidenceSourceKind
    subject_kind: EvidenceSubjectKind
    source: ParticipantLabel | None = None
    subject: ParticipantLabel | None = None


@dataclass(frozen=True, slots=True)
class CommitmentSignatureView:
    """Presentation projection of ``CommitmentSignature`` (§2 C, D-01).

    Differs from the value object in exactly one field: ``subject`` is a
    request-scoped label rather than the durable ``ParticipantId``. The other
    four are verbatim, because the model must see the full signature to propose
    a coherent candidate and to judge bearing under locked §3.3.

    This shape is used in **both** directions: outbound on ``HypothesisView``,
    and inbound on ``CandidateProposal.signature``, where the application
    resolves ``subject`` back to a ``ParticipantId`` before any lineage is
    created or matched. A label that was not supplied in the request fails
    resolution, so the model cannot mint a participant and cannot silently
    re-attribute a commitment.
    """

    subject: ParticipantLabel
    attribution: str
    claim_class: ClaimClass
    stance: Stance
    temporal_scope: str | None = None


@dataclass(frozen=True, slots=True)
class ObservationView:
    """The single record under appraisal (§2 C)."""

    handle: EvidenceHandle
    content: str
    standing: EvidenceStandingView


@dataclass(frozen=True, slots=True)
class HypothesisView:
    """One active hypothesis, by request-scoped handle (§2 C)."""

    handle: HypothesisHandle
    statement: str
    signature: CommitmentSignatureView


@dataclass(frozen=True, slots=True)
class EvidenceCandidateView:
    """One member of the closed divergence-candidate set (§2 J.1)."""

    handle: EvidenceHandle
    content: str
    standing: EvidenceStandingView


@dataclass(frozen=True, slots=True)
class AppraisalRequest:
    """One appraisal call: exactly one observation (§2 C, F-02).

    ``observation`` is singular by construction, which is what makes the
    per-record granularity structural rather than conventional.
    ``divergence_candidates`` is read-only context in the same sense ``existing``
    is; it is never appraised, and selecting from it affects only divergence.
    """

    request_id: str
    subject_id: SubjectId
    space_id: SpaceId
    observation: ObservationView
    existing: tuple[HypothesisView, ...] = ()
    divergence_candidates: tuple[EvidenceCandidateView, ...] = ()


class BearingKind(Enum):
    """Support-axis judgements about an existing hypothesis (§2 C).

    ``DIVERGES_WITH`` is deliberately absent: divergence is evidence<->evidence
    and travels on ``DivergenceProposal``. There is no shape in this response
    type in which a divergence can name a hypothesis (M-01).
    """

    SUPPORTS = "supports"
    WEAKENS = "weakens"
    CONTRADICTS = "contradicts"
    UNCHANGED = "unchanged"


@dataclass(frozen=True, slots=True)
class Bearing:
    """A judgement about one existing hypothesis (§2 C)."""

    target: HypothesisHandle
    kind: BearingKind


@dataclass(frozen=True, slots=True)
class DivergenceProposal:
    """A proposed incompatibility with one already-admitted account (§2 J.1).

    ``with_evidence`` must resolve in ``HandleTable.divergence_candidates``. Both
    endpoints are evidence by construction: this one and the observation under
    appraisal.
    """

    with_evidence: EvidenceHandle
    rationale: str | None = None


@dataclass(frozen=True, slots=True)
class CandidateProposal:
    """A candidate reading (§2 C).

    ``local_ref`` is response-local and never becomes durable. There is no
    ``hypothesis_id`` (the engine issues it after adjudication), no
    ``initial_support`` (R6 fixes the derivation) and no
    ``supporting_evidence_ids`` (support attaches to the single observation
    deterministically).
    """

    local_ref: str
    statement: str
    signature: CommitmentSignatureView


@dataclass(frozen=True, slots=True)
class AppraisalResponse:
    """What an appraiser returns (§2 C). A proposal, not a decision."""

    proposals: tuple[CandidateProposal, ...] = ()
    bearings: tuple[Bearing, ...] = ()
    divergences: tuple[DivergenceProposal, ...] = ()
    raw_response: str | None = None


@runtime_checkable
class EvidenceAppraiser(Protocol):
    """Language-understanding boundary (§2 C).

    Both the External and Scripted implementations satisfy this one signature
    and reach the same call site, which is why the integrity boundary is
    structural rather than duplicated: every governed control lives *after* this
    call, in ``src/sanuvia``.
    """

    def appraise(self, request: AppraisalRequest) -> AppraisalResponse: ...


@runtime_checkable
class CognitiveStateProvider(Protocol):
    """Supplies the participant's current cognitive state (FR-IQ-006)."""

    def current_state(self, subject_id: SubjectId) -> CognitiveState: ...


@runtime_checkable
class RevisionCommitPolicy(Protocol):
    """Decides whether a proposed RevisionEvent commits (FR-MR-003).

    The governing computation is unresolved by the frozen spec; this port exists
    so the engine can defer the decision rather than embed one."""

    def should_commit(self, event: RevisionEvent) -> bool: ...
