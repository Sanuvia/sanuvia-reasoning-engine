"""Persistence adapters.

In-memory implementations are provided for tests and the Phase 0 exit-test
harness. A SQLite (event-sourced) adapter is a later increment; it will satisfy
the same ports with no change to the reasoning engine.
"""

from __future__ import annotations

from .in_memory import InMemoryReasoningStore
from .sqlite_store import SqliteReasoningStore

__all__ = ["InMemoryReasoningStore", "SqliteReasoningStore"]
