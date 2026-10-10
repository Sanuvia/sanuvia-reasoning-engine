"""Stateless foundation-model baseline.

Receives ONLY the current interaction's evidence and retains ZERO reasoning
state between interactions — no persistent hypotheses, support, uncertainty,
revision ledger, or structured evidence history. Each step is an independent
call to the ``LanguageModel``.
"""

from __future__ import annotations

from ..capture import from_baseline_turn, parse_baseline_turn
from ..case import CaseInteraction
from ..failures import BoundaryKind
from ..ports import LanguageModel, LmRequest
from ..trajectory import TrajectoryRecord
from ._prompt import INSTRUCTION, SYSTEM, render_current


class StatelessFmCondition:
    """Foundation-model baseline with no cross-interaction memory."""

    name = "fm_stateless"

    def __init__(self, model: LanguageModel) -> None:
        self._model = model

    def start(self) -> None:
        return None  # nothing to reset; the condition holds no state

    def step(self, interaction: CaseInteraction) -> TrajectoryRecord:
        context = render_current(interaction.evidence)  # current evidence only
        request = LmRequest(system=SYSTEM, context=context, instruction=INSTRUCTION)
        response = self._model.complete(request)
        turn = parse_baseline_turn(response.json_text, BoundaryKind.STATELESS_BASELINE)
        return from_baseline_turn(
            self.name,
            interaction,
            tuple(ev.ref for ev in interaction.evidence),
            turn,
            response.json_text,
        )

    def finish(self) -> None:
        return None
