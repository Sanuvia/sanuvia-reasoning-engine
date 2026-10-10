"""The reasoning-state transaction boundary.

Technical Design v1.5.4 §3.1, §5.3 and §5.5.

Two boundaries are distinguished, because they are not the same boundary:

* the **rollback boundary**, opened by ``ReasoningService.record_interaction``
  at sequence step 0 — *before* the first ``_to_record`` call, and therefore
  before any identifier is allocated;
* the **mutation boundary**, after complete-plan validation at step 13, which is
  the only region in which a store is written.

Opening the rollback boundary first is what puts identifier allocation inside it.
Opening it at the mutation boundary instead would leave every ``evidence-N``
minted at step 2 outside, and a store-only atomicity test would still pass — the
defect F-6 closed.

This introduces no database transaction, no durability and no isolation. It is
the optional capability locked §3.9 permits "only if required by that gap", and
it is required, because no rollback mechanism existed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sanuvia.domain import BreachKind, GovernedOutcome, GovernedRejection


@dataclass
class UnitOfWork:
    """Snapshot/restore around one interaction.

    ``begin()`` captures one opaque token per store in the bundle **plus** the
    identifier-allocation state. ``restore()`` hands each token back.

    Two close operations, one transaction model:

    * ``commit()`` — the path completed, whether or not it wrote anything. The
      no-evidence hold closes this way over an empty plan: it reaches step 14 and
      calls ``commit()``, which writes nothing (§3.6).
    * ``restore()`` — the path was rejected. Carries rejection semantics, which
      is why a hold must not use it: there is nothing to undo, and using it would
      describe a rollback that did not occur and blur the
      ``NO_EVIDENCE_HOLD`` / ``REJECTED_PLAN`` distinction §5.7 depends on.
    """

    stores: dict[str, Any]
    ids: Any | None = None
    _tokens: dict[str, object] = field(default_factory=dict, init=False)
    _ids_token: object | None = field(default=None, init=False)
    _open: bool = field(default=False, init=False)

    def begin(self) -> None:
        """Open the rollback boundary (step 0)."""
        if self._open:
            raise GovernedRejection(
                GovernedOutcome.NON_ATOMIC_REVISION_PLAN,
                "UnitOfWork.begin() called on an already-open unit",
                breach_kind=BreachKind.COMMIT_ATOMICITY,
            )
        self._tokens = {}
        for name, store in self.stores.items():
            snapshot = getattr(store, "snapshot", None)
            if snapshot is None:
                # A store in the bundle without snapshot support would silently
                # escape rollback. §5.1 requires every addition to the bundle to
                # extend coverage, so this is a visible failure, not a skip.
                raise GovernedRejection(
                    GovernedOutcome.NON_ATOMIC_REVISION_PLAN,
                    f"store {name!r} is in the reasoning bundle but is not "
                    f"snapshotable; §5.1 requires snapshot coverage for every store",
                    breach_kind=BreachKind.COMMIT_ATOMICITY,
                )
            self._tokens[name] = snapshot()
        self._ids_token = self.ids.snapshot() if self.ids is not None else None
        self._open = True

    def restore(self) -> None:
        """Roll back stores **and** identifier counters.

        Runs on **every** rejection, pre-mutation included (F-4). Pre-mutation
        there is no store content to revert, but the counters have already
        advanced and are still reinstated.
        """
        if not self._open:
            return
        for name, token in self._tokens.items():
            self.stores[name].restore(token)
        if self.ids is not None and self._ids_token is not None:
            self.ids.restore(self._ids_token)
        self._open = False

    def commit(self) -> None:
        """Close a path that completed. Writes nothing by itself."""
        self._open = False

    @property
    def is_open(self) -> bool:
        return self._open

    def __enter__(self) -> "UnitOfWork":
        self.begin()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        # Any exception -- governed rejection or internal breach -- restores.
        if exc_type is not None:
            self.restore()
        elif self._open:
            self.commit()


def bundle_stores(store: Any) -> dict[str, Any]:
    """Every store in a reasoning bundle, by field name.

    Derived from the bundle's own fields rather than a hard-coded list, so a
    store added later is covered automatically and TD-17b's parametrisation
    grows with it (N-1: "every store in the bundle", not a fixed count).
    """
    fields = getattr(store, "__dataclass_fields__", None)
    if fields is None:
        raise GovernedRejection(
            GovernedOutcome.NON_ATOMIC_REVISION_PLAN,
            "reasoning bundle is not a dataclass; cannot enumerate stores",
            breach_kind=BreachKind.COMMIT_ATOMICITY,
        )
    return {name: getattr(store, name) for name in fields}
