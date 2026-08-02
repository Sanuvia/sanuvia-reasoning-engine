"""Reasoning adapters — Phase-0 placeholder implementations of reasoning ports.

None of these is the "real" version of the responsibility it fills. They exist so
the genuine reasoning engine can run deterministically and be tested without a
foundation model and without inventing spec-unresolved logic inside the core.
Each is explicitly labelled and lives here in the adapter layer, never in the
engine.
"""

from __future__ import annotations

from .cognitive import StaticCognitiveStateProvider
from .commit_policy import PlaceholderCommitAllPolicy
from .scripted_appraiser import ScriptedAppraiser

__all__ = [
    "PlaceholderCommitAllPolicy",
    "StaticCognitiveStateProvider",
    "ScriptedAppraiser",
]
