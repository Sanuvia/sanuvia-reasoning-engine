"""The set of ports the reasoning engine depends on, gathered for wiring.

Every field is typed as a **port** (a Protocol), never a concrete adapter. The
engine is constructed against this bundle, so it remains unaware of which
persistence, clock, id scheme, foundation model, or governance policy is behind
each port. Assembling the bundle from concrete adapters happens at a composition
root (a later increment / the exit-test harness), never inside the engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from sanuvia.application.ports import (
    AnomalyResolutionStore,
    Clock,
    CognitiveStateProvider,
    DependencyGraphStore,
    EvidenceAppraiser,
    EvidenceStore,
    HypothesisRepository,
    IdGenerator,
    InquiryRepository,
    PredictionRepository,
    ProvenanceRepository,
    RecognitionRepository,
    RevisionCommitPolicy,
    RevisionLedgerStore,
    WorldModelRepository,
)
from sanuvia.domain import ReasoningSystemId

from .config import ReasoningConfig


@dataclass(frozen=True)
class ReasoningDependencies:
    """Ports + policy the reasoning engine and Core Loop operate against."""

    reasoning_system_id: ReasoningSystemId
    # persistence ports
    evidence: EvidenceStore
    hypotheses: HypothesisRepository
    predictions: PredictionRepository
    inquiries: InquiryRepository
    world_models: WorldModelRepository
    ledger: RevisionLedgerStore
    anomalies: AnomalyResolutionStore
    provenance: ProvenanceRepository
    recognition: RecognitionRepository
    dependencies: DependencyGraphStore
    # support ports
    clock: Clock
    ids: IdGenerator
    # reasoning ports
    appraiser: EvidenceAppraiser
    cognitive_state: CognitiveStateProvider
    commit_policy: RevisionCommitPolicy
    # Semantic-state persistence ports (Technical Design v1.5.4 §5.1, F-9).
    # Optional so store bundles that predate the semantic-state boundary -- the
    # SQLite adapter, the HTTP test-case store -- keep working unchanged.
    lineages: object | None = None
    statement_versions: object | None = None
    identity_adjudications: object | None = None
    #: The whole bundle, so the service can open a UnitOfWork over every store
    #: by enumeration rather than a fixed list (§5.1, N-1).
    store_bundle: object | None = None
    # tunable policy
    config: ReasoningConfig = ReasoningConfig()
