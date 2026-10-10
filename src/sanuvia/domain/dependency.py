"""Dependency / provenance edges between reasoning objects.

The reasoning objects form a graph: hypotheses are supported or contradicted by
evidence, predictions are derived from hypotheses, inquiries are motivated by
evidence, and evidence supersedes earlier evidence. A ``DependencyEdge`` makes
those links first-class and traceable.

Supersession note (FR-EM-003): supersession is *not* its own object. It is a
relationship between two EvidenceRecords, expressed as a ``SUPERSEDES`` edge and
recorded through revision history (the RevisionLedger) — the immutable evidence
records are never mutated to point at one another.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from .errors import InvariantViolation
from .identifiers import DependencyEdgeId, ObjectRef


class DependencyRelation(Enum):
    """The kind of link a dependency edge expresses."""

    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"  # EvidenceRecord -> EvidenceRecord (FR-EM-003)
    MOTIVATES = "motivates"  # Evidence -> Inquiry
    ACTIVATES = "activates"  # Hypothesis -> Inquiry
    TRACES_TO = "traces_to"  # provenance lineage
    # Symmetric, co-valid divergence between two attributable participant
    # accounts (Technical Design v1.5.4 §2 J). EvidenceRecord <-> EvidenceRecord
    # only: the arity is what keeps divergence off the support axis. Stored as a
    # canonical ordered pair -- see ``canonical_divergence_pair`` -- so symmetry
    # holds by construction rather than by convention. Direction carries no
    # causal meaning and is an ordering artifact.
    DIVERGES_WITH = "diverges_with"


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """A directed, immutable edge ``from_ref --relation--> to_ref``."""

    id: DependencyEdgeId
    from_ref: ObjectRef
    to_ref: ObjectRef
    relation: DependencyRelation
    created_at: datetime

    def __post_init__(self) -> None:
        if self.from_ref == self.to_ref:
            raise InvariantViolation("A DependencyEdge cannot point an object at itself")
        if self.relation is DependencyRelation.DIVERGES_WITH and self.from_ref > self.to_ref:
            raise InvariantViolation(
                "DIVERGES_WITH edges must be stored in canonical order "
                "(from_ref <= to_ref); see Technical Design §2 J"
            )


def canonical_divergence_pair(a: ObjectRef, b: ObjectRef) -> tuple[ObjectRef, ObjectRef]:
    """Order two endpoints canonically for a ``DIVERGES_WITH`` edge (§2 J).

    One edge is stored with ``from_ref = min(a, b)`` and ``to_ref = max(a, b)``,
    so symmetry is guaranteed by construction. Two directed edges were rejected
    because they permit an orphaned half-pair; a separate relation object was
    rejected because it needs a new store and traversal path for one relation.
    """
    if a == b:
        raise InvariantViolation("A record cannot diverge with itself")
    return (a, b) if a <= b else (b, a)
