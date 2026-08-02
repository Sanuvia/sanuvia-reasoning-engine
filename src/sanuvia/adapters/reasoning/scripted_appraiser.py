"""Phase-0 scripted appraiser.

DESIGN NOTE — how candidate hypotheses arise in Phase 0
-------------------------------------------------------
``ScriptedAppraiser`` does **not generate** candidate hypotheses. It performs no
inference. It is a lookup: given an ``EvidenceRecord``, it returns a pre-authored
:class:`Appraisal` keyed by that record's id. The Appraisal is where the scenario
author states, for that piece of evidence, which existing hypotheses it supports
or contradicts and which new candidate explanations (``ProposedHypothesis``) it
introduces — including each candidate's lineage id, opening statement, and
initial support.

Why this is a lookup and not a generator: candidate-hypothesis generation is a
language-understanding task, which the architecture assigns to the *foundation
model* ("FM generates candidate inferences; Sanuvia manages hypotheses and
revises models"). Phase 0 deliberately excludes the FM, so generation is stubbed
by scenario-authored appraisals. In a later phase, an FM-backed ``EvidenceAppraiser``
replaces this class behind the same port; the reasoning engine — which manages,
scores, and revises whatever candidates it receives — does not change.

Consequences worth stating plainly:
* Any "intelligence" in *which* hypotheses appear is authored by the scenario,
  not computed here. The exit test therefore proves the engine *reasons over*
  candidates persistently, not that it *discovers* them.
* Because it is a pure keyed lookup with no clock/randomness, it is fully
  deterministic — the same script yields the same appraisals every run, which is
  required for a reproducible synthetic exit test.
* Unknown evidence yields an empty appraisal: the evidence is recorded but drives
  no hypothesis change.
"""

from __future__ import annotations

from collections.abc import Sequence

from sanuvia.application.ports.reasoning import Appraisal
from sanuvia.domain import EvidenceRecord, EvidenceRecordId, Hypothesis, SubjectId


class ScriptedAppraiser:
    """Returns pre-authored appraisals by evidence id. Implements
    ``EvidenceAppraiser``. Unknown evidence yields an empty appraisal (the
    evidence is recorded but drives no hypothesis change)."""

    def __init__(self, script: dict[EvidenceRecordId, Appraisal] | None = None) -> None:
        self._script: dict[EvidenceRecordId, Appraisal] = dict(script or {})

    def set(self, evidence_id: EvidenceRecordId, appraisal: Appraisal) -> None:
        self._script[evidence_id] = appraisal

    def appraise(
        self,
        subject_id: SubjectId,  # noqa: ARG002
        evidence: EvidenceRecord,
        active_hypotheses: Sequence[Hypothesis],  # noqa: ARG002
    ) -> Appraisal:
        return self._script.get(evidence.id, Appraisal())
