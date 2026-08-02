"""Inquiry (FR-IQ-001 .. FR-IQ-006).

An Inquiry is the engine's representation of a *material uncertainty worth
reducing*. Questions are reasoning operations, not conversation: reasoning
terminates in an Inquiry (never a Recommendation). Not every gap in
understanding becomes an Inquiry (FR-IQ-001).

Traceability constraint (FR-IQ-004): an Inquiry *shall not* be represented as
addressing uncertainty without reference to the Hypotheses and/or Evidence that
justify it. This is enforced as an invariant below.

Status lifecycle (FR-IQ-003): ``proposed -> active -> {dormant, locally_resolved,
reopened, superseded, closed}``. Every status change links to the RevisionEvent
that produced it (recorded at the application layer). The Inquiry record is
immutable; a status change writes a new record retaining the prior one.

OPEN (spec-unresolved — represented, not computed): the *reactivation threshold*
that moves a dormant Inquiry back to active, and the non-convergence measure that
decides when an Inquiry is unresolved rather than merely dormant, are interface-
only in Phase 0. This type models the states; it does not decide the transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .errors import InvariantViolation
from .identifiers import (
    EvidenceRecordId,
    HypothesisId,
    InquiryId,
    RevisionEventId,
    SubjectId,
)
from .uncertainty import ModelUncertainty


class InquiryStatus(Enum):
    """The complete Inquiry status vocabulary (FR-IQ-003)."""

    PROPOSED = "proposed"
    ACTIVE = "active"
    DORMANT = "dormant"
    LOCALLY_RESOLVED = "locally_resolved"
    REOPENED = "reopened"
    SUPERSEDED = "superseded"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class Inquiry:
    """An immutable Inquiry record.

    ``current_uncertainty`` is the model-level uncertainty this Inquiry exists to
    reduce. ``activated_hypothesis_ids`` and ``motivating_evidence_ids`` are the
    justification the traceability constraint requires — at least one must be
    present.
    """

    id: InquiryId
    subject_id: SubjectId
    statement: str
    status: InquiryStatus
    activated_hypothesis_ids: tuple[HypothesisId, ...]
    motivating_evidence_ids: tuple[EvidenceRecordId, ...]
    current_uncertainty: ModelUncertainty
    created_at: datetime
    # The RevisionEvent that produced this (status of this) record, linking the
    # Inquiry's lifecycle into the revision history (FR-IQ-003). None only for
    # an Inquiry proposed outside a revision (rare; represented for completeness).
    produced_by_revision_id: RevisionEventId | None = None

    def __post_init__(self) -> None:
        if not self.statement:
            raise InvariantViolation("Inquiry.statement must be non-empty")
        if not (self.activated_hypothesis_ids or self.motivating_evidence_ids):
            raise InvariantViolation(
                "An Inquiry must reference at least one hypothesis or evidence "
                "record justifying the uncertainty it addresses (FR-IQ-004)"
            )
