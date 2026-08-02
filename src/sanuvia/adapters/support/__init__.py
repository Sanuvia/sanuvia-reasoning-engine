"""Support adapters: concrete Clock and IdGenerator implementations."""

from __future__ import annotations

from .deterministic import ManualClock, SequentialIdGenerator
from .system import SystemClock, UuidGenerator

__all__ = [
    "ManualClock",
    "SequentialIdGenerator",
    "SystemClock",
    "UuidGenerator",
]
