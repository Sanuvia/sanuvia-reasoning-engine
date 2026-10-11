"""The store port Protocols stay runtime-checkable (§5.1, §5.3).

``SnapshotableStore`` lost its ``@runtime_checkable`` decorator when the three
semantic-state Protocols were inserted above it: the insertion consumed the
decorator and left a duplicate on ``HypothesisLineageStore``. A Protocol
without it raises ``TypeError`` on any ``isinstance`` check, so the only thing
that kept the engine running was that the rollback path duck-types
``getattr(store, "snapshot")`` rather than asking the Protocol.

That makes the defect invisible until something *does* ask -- a diagnostic, a
coverage assertion, a later refactor of ``UnitOfWork.begin`` to the declared
port. These tests ask directly, so the decorator cannot go missing again
silently.
"""

from __future__ import annotations

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.application.ports.repositories import (
    HypothesisLineageStore,
    IdentityAdjudicationStore,
    SnapshotableStore,
    StatementVersionStore,
)
from sanuvia.application.reasoning.unit_of_work import UnitOfWork, bundle_stores


def test_snapshotable_store_is_runtime_checkable() -> None:
    """The defining assertion: the isinstance check must not raise TypeError."""
    store = InMemoryReasoningStore()

    assert isinstance(store.evidence, SnapshotableStore)


def test_a_non_snapshotable_object_is_rejected_rather_than_raising() -> None:
    """Runtime-checkable means it answers False, not that it answers at all."""

    class _NotAStore:
        pass

    assert not isinstance(_NotAStore(), SnapshotableStore)


@pytest.mark.parametrize(
    "protocol",
    [HypothesisLineageStore, StatementVersionStore, IdentityAdjudicationStore],
)
def test_the_semantic_state_protocols_are_runtime_checkable(
    protocol: type,
) -> None:
    """The three inserted alongside it, including the one that was decorated
    twice -- a duplicate decorator is not an error, but it is evidence the
    insertion went wrong, and these are the protocols it went wrong between."""
    store = InMemoryReasoningStore()

    assert isinstance(store.lineages, HypothesisLineageStore)
    assert isinstance(store.statement_versions, StatementVersionStore)
    assert isinstance(store.identity_adjudications, IdentityAdjudicationStore)


def test_every_store_in_the_bundle_satisfies_the_snapshot_port() -> None:
    """§5.1: snapshot coverage for every store in the bundle.

    ``UnitOfWork.begin`` enforces this by duck-typing. Asserting it against the
    declared Protocol is what makes the port and the behaviour the same claim.
    """
    store = InMemoryReasoningStore()

    for name, member in bundle_stores(store).items():
        assert isinstance(member, SnapshotableStore), f"{name} is not snapshotable"


def test_the_rollback_path_still_works() -> None:
    """The decorator is a typing fact; rollback behaviour is unchanged."""
    store = InMemoryReasoningStore()
    unit = UnitOfWork(stores=bundle_stores(store))

    unit.begin()
    assert unit.is_open
    unit.restore()
    assert not unit.is_open
