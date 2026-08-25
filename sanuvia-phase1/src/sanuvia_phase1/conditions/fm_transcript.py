"""Transcript-context foundation-model baseline.

Receives the RAW TEXT of the current interaction plus all prior transcript text.
It may have textual continuity, but it holds NONE of Sanuvia's structured state —
no Hypothesis objects, support values, uncertainty, revision ledger, dependency
graph, or WorldModel. The only retained state is the raw transcript buffer.
"""

from __future__ import annotations

from ..capture import from_baseline_turn, parse_baseline_turn
from ..case import CaseInteraction
from ..failures import BoundaryKind
from ..ports import LanguageModel, LmRequest
from ..trajectory import TrajectoryRecord
from ._prompt import INSTRUCTION, SYSTEM, render_lines


class TranscriptContextFmCondition:
    """Foundation-model baseline with raw-text continuity but no structured state."""

    name = "fm_transcript"

    def __init__(self, model: LanguageModel) -> None:
        self._model = model
        self._transcript: list[str] = []

    def start(self) -> None:
        self._transcript = []  # only raw text is ever retained

    def step(self, interaction: CaseInteraction) -> TrajectoryRecord:
        self._transcript.extend(render_lines(interaction.evidence))  # raw text only
        context = "\n".join(self._transcript) if self._transcript else "(no evidence yet)"
        request = LmRequest(system=SYSTEM, context=context, instruction=INSTRUCTION)
        response = self._model.complete(request)
        turn = parse_baseline_turn(response.json_text, BoundaryKind.TRANSCRIPT_BASELINE)
        return from_baseline_turn(
            self.name,
            interaction,
            tuple(ev.ref for ev in interaction.evidence),
            turn,
            response.json_text,
        )

    def finish(self) -> None:
        return None
