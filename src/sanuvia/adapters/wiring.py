"""Composition root helpers.

Wiring is where concrete adapters meet the application's ports. It is the *only*
place that knows both sides. Keeping it here (an adapter concern) means the
reasoning engine never imports a concrete adapter, and swapping a deployment
target — in-memory, SQLite, or a future self-hosted store — is a change confined
to this seam. The two builders below differ *only* in which store bundle they
assemble; the resulting ``ReasoningDependencies`` is identical in shape, so the
engine behaves the same regardless.
"""

from __future__ import annotations

from sanuvia.application.ports.reasoning import (
    CognitiveStateProvider,
    EvidenceAppraiser,
    RevisionCommitPolicy,
)
from sanuvia.application.ports.support import Clock, IdGenerator
from sanuvia.application.reasoning import ReasoningConfig
from sanuvia.application.reasoning.dependencies import ReasoningDependencies
from sanuvia.domain import ReasoningSystemId

from .persistence.in_memory import InMemoryReasoningStore
from .persistence.sqlite_store import SqliteReasoningStore
from .reasoning import PlaceholderCommitAllPolicy, StaticCognitiveStateProvider
from .support import ManualClock, SequentialIdGenerator, SystemClock, UuidGenerator

_StoreBundle = InMemoryReasoningStore | SqliteReasoningStore


def _deps_from_store(
    store: _StoreBundle,
    *,
    reasoning_system_id: str,
    appraiser: EvidenceAppraiser,
    clock: Clock,
    ids: IdGenerator,
    cognitive_state: CognitiveStateProvider | None,
    commit_policy: RevisionCommitPolicy | None,
    config: ReasoningConfig | None,
) -> ReasoningDependencies:
    return ReasoningDependencies(
        reasoning_system_id=ReasoningSystemId(reasoning_system_id),
        evidence=store.evidence,
        hypotheses=store.hypotheses,
        predictions=store.predictions,
        inquiries=store.inquiries,
        world_models=store.world_models,
        ledger=store.ledger,
        anomalies=store.anomalies,
        provenance=store.provenance,
        recognition=store.recognition,
        dependencies=store.dependencies,
        clock=clock,
        ids=ids,
        appraiser=appraiser,
        cognitive_state=cognitive_state or StaticCognitiveStateProvider(),
        commit_policy=commit_policy or PlaceholderCommitAllPolicy(),
        config=config or ReasoningConfig(),
    )


def build_in_memory_dependencies(
    *,
    reasoning_system_id: str = "sanuvia-phase0",
    store: InMemoryReasoningStore | None = None,
    appraiser: EvidenceAppraiser,
    clock: Clock | None = None,
    ids: IdGenerator | None = None,
    cognitive_state: CognitiveStateProvider | None = None,
    commit_policy: RevisionCommitPolicy | None = None,
    config: ReasoningConfig | None = None,
) -> ReasoningDependencies:
    """Assemble ``ReasoningDependencies`` from in-memory adapters (tests / exit
    test). Only the ``appraiser`` (the language-understanding boundary) must be
    supplied, since it encodes the scenario.

    Defaults to the *deterministic* clock/id generator — the in-memory store is
    for reproducible test scenarios (Finding 2)."""
    return _deps_from_store(
        store or InMemoryReasoningStore(),
        reasoning_system_id=reasoning_system_id,
        appraiser=appraiser,
        clock=clock or ManualClock(),
        ids=ids or SequentialIdGenerator(),
        cognitive_state=cognitive_state,
        commit_policy=commit_policy,
        config=config,
    )


def build_sqlite_dependencies(
    *,
    reasoning_system_id: str = "sanuvia-phase0",
    store: SqliteReasoningStore | None = None,
    path: str = ":memory:",
    appraiser: EvidenceAppraiser,
    clock: Clock | None = None,
    ids: IdGenerator | None = None,
    cognitive_state: CognitiveStateProvider | None = None,
    commit_policy: RevisionCommitPolicy | None = None,
    config: ReasoningConfig | None = None,
) -> ReasoningDependencies:
    """Assemble ``ReasoningDependencies`` from the SQLite adapters. Identical in
    shape to the in-memory build — only the persistence backend differs.

    Finding 2 — durable id semantics. SQLite is the *durable* backend, so it
    defaults to a **collision-safe** id generator (``UuidGenerator``) and the
    wall clock. Durable reasoning only ever appends, so ids must be unique across
    the lifetime of the file; a deterministic per-kind counter that restarts at
    ``…-1`` would collide with rows already on disk. Callers that want a
    *deterministic* SQLite run (the review harness's reproducible Test Cases)
    must pass ``ids=SequentialIdGenerator()`` explicitly **and** clear the
    database between runs via ``SqliteReasoningStore.reset()``."""
    return _deps_from_store(
        store or SqliteReasoningStore(path),
        reasoning_system_id=reasoning_system_id,
        appraiser=appraiser,
        clock=clock or SystemClock(),
        ids=ids or UuidGenerator(),
        cognitive_state=cognitive_state,
        commit_policy=commit_policy,
        config=config,
    )
