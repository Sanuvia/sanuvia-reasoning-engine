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

from collections.abc import Sequence

from sanuvia.application.ports.reasoning import Appraisal
from sanuvia.domain import EvidenceRecord, Hypothesis, SubjectId


class HarnessAppraiser:
    """Returns the appraisal the reviewer supplied for the current submission."""

    def __init__(self) -> None:
        self._pending = Appraisal()

    def set_pending(self, appraisal: Appraisal) -> None:
        self._pending = appraisal

    def appraise(
        self,
        subject_id: SubjectId,  # noqa: ARG002
        evidence: EvidenceRecord,  # noqa: ARG002
        active_hypotheses: Sequence[Hypothesis],  # noqa: ARG002
    ) -> Appraisal:
        appraisal = self._pending
        self._pending = Appraisal()  # consume; unappraised evidence is just recorded
        return appraisal
