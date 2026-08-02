"""Support ports: time, id generation, and foundation-model access.

These are the seams that keep the domain free of clocks, randomness, and any
foundation model. The domain never calls ``datetime.now()`` or generates ids;
the application asks these ports, and adapters supply concrete implementations.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Supplies the current time. Injected so reasoning is deterministic in
    tests and free of ambient wall-clock access."""

    def now(self) -> datetime:
        """Return the current time as a timezone-aware ``datetime``."""
        ...


@runtime_checkable
class IdGenerator(Protocol):
    """Supplies opaque, unique id strings. The domain treats ids as opaque, so
    any collision-free scheme (UUIDs, ULIDs, test counters) is acceptable."""

    def new_id(self, kind: str) -> str:
        """Return a fresh unique id. ``kind`` is a hint (e.g. ``"evidence"``)
        adapters may use for prefixing/readability; the domain never parses it."""
        ...


@runtime_checkable
class ModelProvider(Protocol):
    """Port for a foundation model — DEFERRED for Phase 0.

    Foundation models are *replaceable infrastructure*: the reasoning engine
    stays independent of any one vendor. This port exists so that later phases
    can plug an LLM in behind it (for language understanding / candidate
    inference generation) without the domain or application core changing.

    Phase 0 runs deterministically and does **not** require an implementation of
    this port. It is defined here only to fix the seam.
    """

    def complete(self, prompt: str) -> str:
        """Produce a completion for ``prompt``. Not used in Phase 0."""
        ...
