"""The ReasoningCondition contract.

Each condition is driven through the *same* immutable interaction sequence. A
condition owns its own state (Sanuvia: the frozen engine + store; FM baselines:
either nothing, or raw transcript text) and emits one normalized
``TrajectoryRecord`` per interaction.
"""

from __future__ import annotations

from typing import Protocol

from ..case import CaseInteraction
from ..trajectory import TrajectoryRecord


class ReasoningCondition(Protocol):
    """A comparison condition. State ownership is explicit and per-condition."""

    name: str

    def start(self) -> None:
        """Reset to a fresh, isolated state for a new demonstration run."""
        ...

    def step(self, interaction: CaseInteraction) -> TrajectoryRecord:
        """Process one interaction (which may carry no new evidence) and record it."""
        ...

    def finish(self) -> None:
        """Signal end of sequence (hook for teardown / summaries)."""
        ...
