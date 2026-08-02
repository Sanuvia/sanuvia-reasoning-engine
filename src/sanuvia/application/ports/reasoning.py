"""Reasoning ports — seams for decisions the frozen spec assigns elsewhere or
leaves unresolved.

Keeping these behind interfaces is what lets the reasoning engine be *genuine*
without *faking* deferred logic:

* ``EvidenceAppraiser`` — the language-understanding boundary. Deciding which
  hypotheses a piece of evidence supports or contradicts, and proposing new
  candidate explanations, is the *foundation model's* responsibility per the
  architecture ("FM generates candidate inferences; Sanuvia manages hypotheses
  and revises models"). Phase 0 supplies a deterministic, scripted adapter; a
  later phase plugs an LLM in behind the same port. Hypothesis *identity/creation*
  is spec-unresolved, so the appraiser supplies the ``hypothesis_id`` — the engine
  does not invent one.

* ``CognitiveStateProvider`` — ``get_user_cognitive_state`` (FR-IQ-006). A single
  enum in Phase 0 (multi-dimensional CognitiveState is an explicit non-goal).

* ``RevisionCommitPolicy`` — the ``proposed -> committed`` transition governance
  (FR-MR-003) that the frozen spec explicitly does not resolve. The engine
  *asks* this policy; it does not embed a governance rule. The Phase-0 adapter is
  a loudly-labelled placeholder, not the real governance.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sanuvia.domain import (
    CognitiveState,
    EvidenceRecord,
    EvidenceRecordId,
    FutureTrajectory,
    Hypothesis,
    HypothesisId,
    RevisionEvent,
    SubjectId,
)


@dataclass(frozen=True, slots=True)
class ProposedHypothesis:
    """A candidate explanation proposed from evidence.

    ``hypothesis_id`` is the lineage identity. Because how hypothesis identity is
    computed is unresolved by the frozen spec, the appraiser supplies it rather
    than the engine deriving one. ``predicted_trajectory`` optionally carries a
    language-understanding hint the engine may turn into a Prediction.
    """

    hypothesis_id: HypothesisId
    statement: str
    initial_support: float
    supporting_evidence_ids: tuple[EvidenceRecordId, ...]
    predicted_trajectory: FutureTrajectory | None = None


@dataclass(frozen=True, slots=True)
class Appraisal:
    """The appraisal of a single evidence record against current understanding.

    ``supports`` / ``contradicts`` reference existing hypotheses by lineage id;
    ``proposals`` are new candidate explanations. All three may be empty (e.g. a
    failed acquisition that yields only competing proposals, or evidence that is
    merely noted)."""

    supports: tuple[HypothesisId, ...] = ()
    contradicts: tuple[HypothesisId, ...] = ()
    proposals: tuple[ProposedHypothesis, ...] = field(default=())


@runtime_checkable
class EvidenceAppraiser(Protocol):
    """Language-understanding boundary (FM in later phases; scripted in Phase 0)."""

    def appraise(
        self,
        subject_id: SubjectId,
        evidence: EvidenceRecord,
        active_hypotheses: Sequence[Hypothesis],
    ) -> Appraisal: ...


@runtime_checkable
class CognitiveStateProvider(Protocol):
    """Supplies the participant's current cognitive state (FR-IQ-006)."""

    def current_state(self, subject_id: SubjectId) -> CognitiveState: ...


@runtime_checkable
class RevisionCommitPolicy(Protocol):
    """Decides whether a proposed RevisionEvent commits (FR-MR-003).

    The governing computation is unresolved by the frozen spec; this port exists
    so the engine can defer the decision rather than embed one."""

    def should_commit(self, event: RevisionEvent) -> bool: ...
