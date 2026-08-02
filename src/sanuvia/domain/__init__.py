"""Sanuvia domain layer — the reasoning objects and their invariants.

This layer is pure: standard library only, no framework, no cloud SDK, no
foundation model, no I/O. It is the single source of truth for the data model
regardless of where the system is deployed.

Every object traces to a frozen FR-* requirement; see each module's docstring.
"""

from __future__ import annotations

from .cognitive import AcquisitionStrategy, CognitiveState
from .dependency import DependencyEdge, DependencyRelation
from .errors import (
    DomainError,
    EvidenceInferenceConflation,
    InvariantViolation,
    NotYetSpecified,
)
from .evidence import (
    EvidenceClass,
    EvidenceRecord,
    InferenceRecord,
    Provenance,
)
from .hypothesis import Hypothesis
from .identifiers import (
    AnomalyResolutionId,
    DependencyEdgeId,
    EvidenceRecordId,
    HypothesisId,
    HypothesisRecordId,
    InferenceRecordId,
    InquiryId,
    ObjectRef,
    PredictionId,
    ProvenanceRecordId,
    ReasoningSystemId,
    RecognitionEventId,
    RevisionEventId,
    SubjectId,
    SystemModellingContextId,
    WorldModelVersionId,
)
from .inquiry import Inquiry, InquiryStatus
from .prediction import FutureTrajectory, Prediction, TrajectoryKind
from .recognition import RecognitionEvent, RecognitionKind
from .revision import (
    AnomalyDisposition,
    AnomalyResolution,
    ModelRevisionResult,
    RevisionEvent,
    RevisionLedgerEntry,
    RevisionOutcome,
    RevisionStatus,
)
from .uncertainty import (
    ClassificationConfidence,
    EvidenceReliability,
    HypothesisSupport,
    ModelUncertainty,
    PredictionLikelihood,
    ProvenanceConfidence,
)
from .world_model import (
    CurrentModelSnapshot,
    ProvenanceRecord,
    SystemModellingContext,
    WorldModel,
)

__all__ = [
    # errors
    "DomainError",
    "InvariantViolation",
    "EvidenceInferenceConflation",
    "NotYetSpecified",
    # identifiers
    "SubjectId",
    "ReasoningSystemId",
    "EvidenceRecordId",
    "InferenceRecordId",
    "WorldModelVersionId",
    "ProvenanceRecordId",
    "SystemModellingContextId",
    "HypothesisId",
    "HypothesisRecordId",
    "PredictionId",
    "InquiryId",
    "RevisionEventId",
    "AnomalyResolutionId",
    "RecognitionEventId",
    "DependencyEdgeId",
    "ObjectRef",
    # uncertainty (six typed values)
    "EvidenceReliability",
    "HypothesisSupport",
    "ModelUncertainty",
    "ClassificationConfidence",
    "ProvenanceConfidence",
    "PredictionLikelihood",
    # evidence
    "EvidenceClass",
    "Provenance",
    "EvidenceRecord",
    "InferenceRecord",
    # reasoning
    "Hypothesis",
    "Prediction",
    "FutureTrajectory",
    "TrajectoryKind",
    # inquiry
    "Inquiry",
    "InquiryStatus",
    # revision
    "AnomalyDisposition",
    "AnomalyResolution",
    "RevisionOutcome",
    "RevisionStatus",
    "RevisionEvent",
    "ModelRevisionResult",
    "RevisionLedgerEntry",
    # persistent understanding
    "WorldModel",
    "CurrentModelSnapshot",
    "ProvenanceRecord",
    "SystemModellingContext",
    # recognition
    "RecognitionEvent",
    "RecognitionKind",
    # dependency
    "DependencyEdge",
    "DependencyRelation",
    # cognitive
    "CognitiveState",
    "AcquisitionStrategy",
]
