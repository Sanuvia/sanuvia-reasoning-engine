"""Phase 1 ports — the replaceable boundaries.

Only one port is defined here: :class:`LanguageModel`, the seam behind which the
two foundation-model baseline conditions run. Keeping it a Protocol lets us use a
deterministic test double (``ScriptedLanguageModel``) in CI and a real adapter
(``ExternalLanguageModel``) for opt-in evaluation, without either baseline
depending on a specific vendor.

The Sanuvia Persistent condition deliberately has **no** language-model port — it
is the frozen Phase 0 reasoning engine and uses no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class LmRequest:
    """A prompt for a baseline language model.

    ``system`` states the task and the constrained-JSON response contract;
    ``context`` is the evidence the condition is allowed to show (current-only
    for stateless, full transcript for transcript-context); ``instruction`` asks
    for the structured answer. The request carries no Sanuvia structured state.
    """

    system: str
    context: str
    instruction: str


@dataclass(frozen=True, slots=True)
class LmResponse:
    """A language model's raw reply — expected to be a single JSON object string
    conforming to the Phase 1 response contract (see ``capture.parse_baseline_turn``)."""

    json_text: str


@runtime_checkable
class LanguageModel(Protocol):
    """A foundation-model boundary for the baseline conditions.

    Implementations: ``ScriptedLanguageModel`` (deterministic test double, the
    default CI path) and ``ExternalLanguageModel`` (real adapter seam, opt-in).
    """

    def complete(self, request: LmRequest) -> LmResponse: ...
