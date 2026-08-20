"""Typed identifiers for domain objects.

Each object type gets a distinct ``NewType`` over ``str`` ("branded" ids). This
is deliberate: it lets the type checker reject, for example, passing a
``HypothesisId`` where an ``EvidenceRecordId`` is expected. Ids are opaque
strings — the domain never parses or derives meaning from their contents.

Ids are *supplied* to the domain (via the ``IdGenerator`` port at the
application boundary); the domain never generates them itself, so it stays
free of clocks, randomness, and I/O.
"""

from __future__ import annotations

from typing import NewType

# --- Space / subject / actor scoping ------------------------------------------
# Three distinct identifiers that must never be collapsed into one another
# (Finding 1 — subject/space/actor isolation):
#
#   * SpaceId   — *where* the reasoning belongs: the isolation / access boundary.
#                 All reasoning state (evidence, hypotheses, predictions, world
#                 models, ledger) is partitioned by space. Two spaces never see
#                 each other's reasoning.
#   * SubjectId — *who or what* the reasoning concerns, within a space.
#   * ActorId   — *who contributed* a piece of evidence or performed an action
#                 (a.k.a. member id). It records provenance of contribution and
#                 is never a partition key on its own.
SpaceId = NewType("SpaceId", str)
"""The isolation/access boundary a piece of reasoning belongs to (Finding 1)."""

SubjectId = NewType("SubjectId", str)
"""The reasoning participant a WorldModel and its evidence are scoped to
(FR-PU-001/002). Scoped *within* a :data:`SpaceId`."""

ActorId = NewType("ActorId", str)
"""Who contributed the evidence / performed the action (a.k.a. member id). It is
a contribution-provenance identifier, not an isolation boundary."""

ReasoningSystemId = NewType("ReasoningSystemId", str)
"""A key referenced across schemas, not a stored object (per ownership map)."""

# --- Evidence Management ------------------------------------------------------
EvidenceRecordId = NewType("EvidenceRecordId", str)  # FR-EM-001
InferenceRecordId = NewType("InferenceRecordId", str)  # FR-EM-005

# --- Persistent Understanding -------------------------------------------------
WorldModelVersionId = NewType("WorldModelVersionId", str)  # FR-PU-001/003
ProvenanceRecordId = NewType("ProvenanceRecordId", str)  # FR-PU-004
SystemModellingContextId = NewType("SystemModellingContextId", str)  # FR-PU-005

# --- Reasoning ----------------------------------------------------------------
HypothesisId = NewType("HypothesisId", str)  # FR-RS-001 (lineage identity)
HypothesisRecordId = NewType("HypothesisRecordId", str)  # immutable version id
PredictionId = NewType("PredictionId", str)  # FR-RS-004

# --- Inquiry ------------------------------------------------------------------
InquiryId = NewType("InquiryId", str)  # FR-IQ-001

# --- Model Revision -----------------------------------------------------------
RevisionEventId = NewType("RevisionEventId", str)  # FR-MR-001
AnomalyResolutionId = NewType("AnomalyResolutionId", str)  # FR-MR-004

# --- Reflection / Recognition -------------------------------------------------
RecognitionEventId = NewType("RecognitionEventId", str)  # FR-RF-001

# --- Cross-cutting ------------------------------------------------------------
DependencyEdgeId = NewType("DependencyEdgeId", str)

ObjectRef = NewType("ObjectRef", str)
"""An untyped reference to *any* domain object by its id string. Used where a
field must point at a heterogeneous object (e.g. a RevisionEvent's
``affected_object_id`` or a DependencyEdge endpoint). Prefer a branded id where
the referent type is fixed."""
