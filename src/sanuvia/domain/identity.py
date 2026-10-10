"""Semantic identity decisions and the parked adjudication record.

Technical Design v1.5.4 §2 D and §2 G.

The model proposes candidate language; the **engine** issues every durable
hypothesis id, and only after adjudication. These types carry the decision and,
where the decision is to park, the durable record that preserves the candidate
without creating or revising a hypothesis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .errors import InvariantViolation
from .hypothesis import CommitmentSignature
from .identifiers import (
    EvidenceRecordId,
    HypothesisId,
    IdentityAdjudicationId,
    RevisionEventId,
    SpaceId,
    SubjectId,
)
from .scope import DEFAULT_SPACE_ID


class IdentityOutcome(Enum):
    """The four governed identity outcomes (locked §3.3)."""

    MATCH_EXISTING = "MATCH_EXISTING"
    REFINE_EXISTING = "REFINE_EXISTING"
    DISTINCT_NEW = "DISTINCT_NEW"
    AMBIGUOUS_REVIEW_REQUIRED = "AMBIGUOUS_REVIEW_REQUIRED"


class AdjudicationStatus(Enum):
    """Lifecycle of a parked candidate.

    Ruling Q2: Run 003 **creates, preserves and reports** parked candidates and
    implements no resolution path. Nothing sets ``RESOLVED``; the value exists
    for the later governed cycle that implements the transition locked §3.3
    describes.
    """

    PARKED = "PARKED"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True, slots=True)
class IdentityDecision:
    """One adjudication result (§2 G).

    ``matched_in_flight`` records which arm matched, so the audit distinguishes
    "matched something the system already believed" from "matched something
    proposed moments earlier in this same plan".

    ``matched_lineage_key`` is the **plan-local** reference used before durable
    ids are issued at step 9 (F-16). Plan-local lineage keys are not
    proposal-local refs and are deliberately out of scope for check 5.
    """

    outcome: IdentityOutcome
    candidate_local_ref: str
    matched_hypothesis_id: HypothesisId | None = None
    matched_lineage_key: tuple[str, str] | None = None
    matched_in_flight: bool = False
    plausible_matches: tuple[HypothesisId, ...] = ()
    rationale: str | None = None
    #: Provenance only (F-8). There is no threshold, no minimum constant, no
    #: low-confidence automatic parking and no confidence-based rewriting of the
    #: returned outcome. It is recorded and reported; it never changes an outcome.
    confidence: float | None = None
    resolver_id: str | None = None
    resolver_raw_response: str | None = None
    #: Set when the application discarded a resolver outcome under R1a.
    overridden_resolver_outcome: IdentityOutcome | None = None


@dataclass(frozen=True, slots=True)
class IdentityAdjudication:
    """A parked candidate (§2 D).

    Creates and revises **no** hypothesis. It survives holds because the hold
    path performs no writes at all. A reasoning-store write, so it lives in
    ``IdentityAdjudicationStore`` and participates in snapshot/restore.
    """

    id: IdentityAdjudicationId
    subject_id: SubjectId
    candidate_statement: str
    candidate_signature: CommitmentSignature
    decision: IdentityDecision
    created_at: datetime
    source_evidence_ids: tuple[EvidenceRecordId, ...] = ()
    plausible_matches: tuple[HypothesisId, ...] = ()
    created_by_revision_id: RevisionEventId | None = None
    status: AdjudicationStatus = AdjudicationStatus.PARKED
    space_id: SpaceId = DEFAULT_SPACE_ID

    def __post_init__(self) -> None:
        if not self.candidate_statement:
            raise InvariantViolation(
                "IdentityAdjudication.candidate_statement must be non-empty"
            )
        if self.decision.outcome is not IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED:
            raise InvariantViolation(
                "IdentityAdjudication records only AMBIGUOUS_REVIEW_REQUIRED "
                f"candidates; got {self.decision.outcome.value}"
            )
