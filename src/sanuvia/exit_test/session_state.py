"""SessionState — an immutable handle onto one reasoning session's state.

Both the reasoning trace and the reasoning lineage graph are *pure renderers*
over this handle. It bundles the per-interaction results the engine returned
together with read access (via the existing repository ports) to the persisted
immutable state: WorldModel versions, the RevisionLedger, Evidence, Hypotheses,
Predictions, Inquiries, Provenance, and Recognition events.

The renderers therefore have exactly one source of truth — the engine's own
state — and work identically for a live review session or the canonical
exit-test scenario. The reasoning engine is not involved in rendering.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sanuvia.application.ports.repositories import (
    EvidenceStore,
    HypothesisRepository,
    InquiryRepository,
    PredictionRepository,
    ProvenanceRepository,
    RecognitionRepository,
    RevisionLedgerStore,
    WorldModelRepository,
)
from sanuvia.application.reasoning.core_loop import InteractionResult
from sanuvia.domain import SubjectId


@dataclass(frozen=True)
class SessionState:
    """Read-only view of one session's reasoning state for rendering."""

    subject_id: SubjectId
    interactions: tuple[InteractionResult, ...]
    evidence: EvidenceStore
    hypotheses: HypothesisRepository
    predictions: PredictionRepository
    inquiries: InquiryRepository
    world_models: WorldModelRepository
    ledger: RevisionLedgerStore
    provenance: ProvenanceRepository
    recognition: RecognitionRepository


def canonical_session_state() -> SessionState:
    """Run the canonical exit-test scenario and expose it as a SessionState.

    This is the *reference* mode — the same fixed scenario the exit test uses. It
    is one producer of a SessionState among others (a live review session is
    another); the renderers do not know or care which.
    """
    # Imported lazily to avoid a module-load cycle (scenario imports adapters).
    from .scenario import SUBJECT, build

    harness = build()
    results = tuple(
        harness.service.record_interaction(SUBJECT, [item])
        for item in harness.inputs
    )
    s = harness.store
    return SessionState(
        subject_id=SUBJECT,
        interactions=results,
        evidence=s.evidence,
        hypotheses=s.hypotheses,
        predictions=s.predictions,
        inquiries=s.inquiries,
        world_models=s.world_models,
        ledger=s.ledger,
        provenance=s.provenance,
        recognition=s.recognition,
    )


def from_interactions(
    subject_id: SubjectId,
    interactions: Sequence[InteractionResult],
    store: object,
) -> SessionState:
    """Build a SessionState from a live session's results and its store bundle.

    ``store`` is any object exposing the repository attributes (the in-memory or
    SQLite bundle). Kept as ``object`` + attribute access so this module stays
    independent of concrete adapters.
    """
    return SessionState(
        subject_id=subject_id,
        interactions=tuple(interactions),
        evidence=getattr(store, "evidence"),
        hypotheses=getattr(store, "hypotheses"),
        predictions=getattr(store, "predictions"),
        inquiries=getattr(store, "inquiries"),
        world_models=getattr(store, "world_models"),
        ledger=getattr(store, "ledger"),
        provenance=getattr(store, "provenance"),
        recognition=getattr(store, "recognition"),
    )
