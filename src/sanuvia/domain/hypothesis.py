"""Hypothesis (FR-RS-001/002/003).

A hypothesis is a *provisional* explanation of observed patterns — never a
conclusion, diagnosis, or statement about a person's character. The engine may
hold **multiple competing hypotheses simultaneously** (FR-RS-001); competing
explanations are the accurate representation of incomplete understanding, not a
failure of reasoning.

Immutability & re-evaluation. A ``Hypothesis`` record is immutable. Re-evaluation
does not overwrite it: a new immutable record is written and the prior value is
retained in revision history (FR-RS-003). We therefore separate two ids:

* ``hypothesis_id``  — stable *lineage* identity across re-evaluations.
* ``record_id``      — this specific immutable version.

OPEN (spec-unresolved): what computation decides whether new evidence updates an
existing hypothesis (same ``hypothesis_id``) or creates a genuinely new one, and
what governs hypothesis identity, is **not specified**. The domain models both
ids so the distinction is representable, but assigns no such logic. There is also
deliberately **no lifecycle status enum** on Hypothesis (unlike Inquiry) — the
frozen spec defines none.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .errors import InvariantViolation
from .identifiers import (
    EvidenceRecordId,
    HypothesisId,
    HypothesisRecordId,
    SpaceId,
    SubjectId,
    WorldModelVersionId,
)
from .scope import DEFAULT_SPACE_ID
from .uncertainty import HypothesisSupport


@dataclass(frozen=True, slots=True)
class Hypothesis:
    """One immutable evaluation of a competing explanation.

    ``support`` is the explicit degree to which current evidence supports it
    (FR-RS-002). Support is a *mandatory* attached uncertainty and is never
    omitted (FR-RS-005). Supporting and contradicting evidence are tracked
    separately so contradiction is preserved rather than collapsed.
    """

    record_id: HypothesisRecordId
    hypothesis_id: HypothesisId
    # Who this hypothesis concerns (Finding 1). A hypothesis is owned by exactly
    # one subject; the repositories partition by it so a hypothesis can never be
    # returned for another subject.
    subject_id: SubjectId
    statement: str
    support: HypothesisSupport
    supporting_evidence_ids: tuple[EvidenceRecordId, ...]
    contradicting_evidence_ids: tuple[EvidenceRecordId, ...]
    # The WorldModel version at which this evaluation was recorded.
    evaluated_at_version: WorldModelVersionId
    evaluated_at: datetime
    # If this record re-evaluates a prior one, the prior *record* it supersedes
    # (retained, never overwritten — FR-RS-003). None for the first evaluation.
    supersedes_record_id: HypothesisRecordId | None = None
    # Isolation boundary this hypothesis belongs to (Finding 1).
    space_id: SpaceId = DEFAULT_SPACE_ID

    def __post_init__(self) -> None:
        if not self.statement:
            raise InvariantViolation("Hypothesis.statement must be non-empty")
        if not self.space_id:
            raise InvariantViolation("Hypothesis.space_id must be non-empty")
        overlap = set(self.supporting_evidence_ids) & set(
            self.contradicting_evidence_ids
        )
        if overlap:
            raise InvariantViolation(
                "The same evidence cannot both support and contradict a "
                f"hypothesis: {sorted(overlap)}"
            )
