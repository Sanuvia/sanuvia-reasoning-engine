"""HarnessAppraiser — relays a reviewer's structured appraisal to the engine.

The Phase 0 engine has no foundation model, so evidence appraisal (which
hypotheses an observation supports/contradicts, and any new candidate
explanations) must be supplied. In the exit test that is a ``ScriptedAppraiser``
keyed by evidence id. In the review harness the reviewer supplies the appraisal
with each submission; this adapter simply holds the *pending* appraisal and
returns it for the next observation.

It implements the existing ``EvidenceAppraiser`` port and contains **no
reasoning** — it is a relay. All reasoning stays in the engine. This is the same
language-understanding seam an FM-backed appraiser would fill in a later phase;
it must not grow into a conversation/NLP layer here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sanuvia.adapters.reasoning.scripted_appraiser import ScriptedAppraiser

from collections.abc import Sequence

from sanuvia.application.ports.reasoning import (
    Appraisal,
    AppraisalRequest,
    AppraisalResponse,
)
from sanuvia.domain import EvidenceRecord, Hypothesis, SubjectId


class HarnessAppraiser:
    """Returns the appraisal the reviewer supplied for the current submission."""

    def __init__(self) -> None:
        self._pending = Appraisal()
        # One translator for the life of the harness, so the authored-id ->
        # statement catalogue accumulates across submissions. A later
        # ``supports=(H,)`` can then resolve the lineage H named, which a
        # per-call translator could not.
        self._translator: "ScriptedAppraiser | None" = None

    def set_pending(self, appraisal: Appraisal) -> None:
        self._pending = appraisal

    def appraise(self, request: "AppraisalRequest") -> "AppraisalResponse":
        """Translate the reviewer's authored appraisal into handle space.

        Conforms to the Technical Design v1.5.4 port. The translation is
        delegated to ``ScriptedAppraiser`` so the harness and the Phase 0 test
        double share one migration path -- including the explicit fixture
        signature assumptions A1-A3 recorded there.
        """
        from sanuvia.adapters.reasoning.scripted_appraiser import ScriptedAppraiser

        appraisal = self._pending
        self._pending = Appraisal()  # consume; unappraised evidence is just recorded
        if request.observation_id is None:
            return AppraisalResponse()
        if self._translator is None:
            self._translator = ScriptedAppraiser({})
        self._translator.set(request.observation_id, appraisal)
        return self._translator.appraise(request)
