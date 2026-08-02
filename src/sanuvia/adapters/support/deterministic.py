"""Deterministic Clock and IdGenerator adapters.

Used to make reasoning runs (and their tests / the exit-test harness) fully
reproducible. They satisfy the ``Clock`` and ``IdGenerator`` ports without any
ambient wall-clock or randomness.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


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
