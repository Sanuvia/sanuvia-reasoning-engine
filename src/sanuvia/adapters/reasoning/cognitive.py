"""Phase-0 cognitive-state provider placeholder.

A structured, multi-dimensional CognitiveState is an explicit non-goal for
Phase 0. This adapter returns a fixed single-enum state (default ``ENGAGED``),
optionally overridable per subject for scenario testing. It stands in for a real
cognitive-state inference that a later phase would supply.
"""

from __future__ import annotations

from sanuvia.domain import CognitiveState, SubjectId


class StaticCognitiveStateProvider:
    """Returns a fixed cognitive state. Implements ``CognitiveStateProvider``."""

    def __init__(
        self,
        default: CognitiveState = CognitiveState.ENGAGED,
        *,
        overrides: dict[SubjectId, CognitiveState] | None = None,
    ) -> None:
        self._default = default
        self._overrides = dict(overrides or {})

    def set_state(self, subject_id: SubjectId, state: CognitiveState) -> None:
        self._overrides[subject_id] = state

    def current_state(self, subject_id: SubjectId) -> CognitiveState:
        return self._overrides.get(subject_id, self._default)
