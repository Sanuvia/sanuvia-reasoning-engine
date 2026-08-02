"""Cognitive state and acquisition strategy (FR-IQ-006).

These support the Core Loop's ``get_user_cognitive_state`` and
``select_acquisition_strategy`` steps. Cognitive state acts as a *feasibility
gate* on evidence acquisition — it constrains the form of acquisition, it does
not replace the uncertainty-driven prioritisation that FR-IQ-005 governs.

Scope note (deliberate simplification): a structured, multi-dimensional
``CognitiveState`` is an **explicit non-goal** for Phase 0. It is represented here
as a single enum, matching the frozen spec's acknowledged simplification. Do not
build the multi-dimensional version in this phase.

Ownership of ``CognitiveState`` / ``AcquisitionStrategy`` is unresolved in the
frozen spec (no domain confirmed to own either). They live in the domain as
value types so the Core Loop can reference them, without asserting an owner.
"""

from __future__ import annotations

from enum import Enum


class CognitiveState(Enum):
    """A single-enum approximation of the participant's current capacity to
    engage. A feasibility gate on acquisition, not a replacement input."""

    UNKNOWN = "unknown"
    ENGAGED = "engaged"
    NEUTRAL = "neutral"
    REDUCED_CAPACITY = "reduced_capacity"
    DISTRESSED = "distressed"


class AcquisitionStrategy(Enum):
    """How the engine will seek the next piece of evidence. Under reduced
    capacity the engine favours minimal/passive acquisition (FR-IQ-006)."""

    PASSIVE = "passive"
    MINIMAL = "minimal"
    ACTIVE = "active"
    TARGETED = "targeted"
