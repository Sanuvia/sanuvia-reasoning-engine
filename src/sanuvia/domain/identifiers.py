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

# --- Subject / system scoping -------------------------------------------------
SubjectId = NewType("SubjectId", str)
"""The reasoning participant a WorldModel and its evidence are scoped to
(FR-PU-001/002)."""

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
