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
