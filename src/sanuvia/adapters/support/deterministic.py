"""Deterministic Clock and IdGenerator adapters.

Used to make reasoning runs (and their tests / the exit-test harness) fully
reproducible. They satisfy the ``Clock`` and ``IdGenerator`` ports without any
ambient wall-clock or randomness.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import cast


class ManualClock:
    """A clock the caller advances explicitly. Implements the ``Clock`` port."""

    def __init__(self, start: datetime | None = None, *, step_seconds: int = 1) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
        self._step = timedelta(seconds=step_seconds)

    def now(self) -> datetime:
        return self._now

    def tick(self) -> datetime:
        """Advance by one step and return the new time."""
        self._now = self._now + self._step
        return self._now


class SequentialIdGenerator:
    """Monotonic, per-kind counter ids (e.g. ``evidence-1``). Implements the
    ``IdGenerator`` port. Deterministic and readable for tests."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def new_id(self, kind: str) -> str:
        n = self._counters.get(kind, 0) + 1
        self._counters[kind] = n
        return f"{kind}-{n}"

    # -- snapshot/restore (Technical Design v1.5.4 §5.5, F-6) ----------------
    #
    # Identifier-allocation state is mutable and sits OUTSIDE the store bundle,
    # but canonical ``evidence-N`` ids are minted at sequence step 2 and durable
    # hypothesis ids during step 9 -- both before any store write. If the counter
    # were not restored, a rejected plan would permanently consume identifiers and
    # the next interaction's ids would differ from what they would have been,
    # which is not byte-equivalent. ``restore()`` therefore runs on EVERY
    # rejection, pre-mutation included (F-4).
    def snapshot(self) -> object:
        return dict(self._counters)

    def restore(self, token: object) -> None:
        self._counters = dict(cast("dict[str, int]", token))
