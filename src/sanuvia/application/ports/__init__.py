"""Ports — the interfaces the application depends on.

Persistence ports live in :mod:`.repositories`; time / id / foundation-model
ports live in :mod:`.support`. Adapters implement these; the core never imports
an adapter.
"""

from __future__ import annotations

from .repositories import (
    AnomalyResolutionStore,
    DependencyGraphStore,
    EvidenceStore,
    HypothesisRepository,
    InferenceStore,
    InquiryRepository,
    PredictionRepository,
    ProvenanceRepository,
    RecognitionRepository,
    RevisionLedgerStore,
    SystemModellingContextStore,
    WorldModelRepository,
)
from .reasoning import (
    Appraisal,
    CognitiveStateProvider,
    EvidenceAppraiser,
    ProposedHypothesis,
    RevisionCommitPolicy,
)
from .support import Clock, IdGenerator, ModelProvider

__all__ = [
    # repositories
    "EvidenceStore",
    "InferenceStore",
    "HypothesisRepository",
    "PredictionRepository",
    "InquiryRepository",
    "WorldModelRepository",
    "RevisionLedgerStore",
    "AnomalyResolutionStore",
    "ProvenanceRepository",
    "RecognitionRepository",
    "DependencyGraphStore",
    "SystemModellingContextStore",
    # support
    "Clock",
    "IdGenerator",
    "ModelProvider",
    # reasoning
    "EvidenceAppraiser",
    "Appraisal",
    "ProposedHypothesis",
    "CognitiveStateProvider",
    "RevisionCommitPolicy",
]
