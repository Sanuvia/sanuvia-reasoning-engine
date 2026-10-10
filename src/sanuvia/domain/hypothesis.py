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
from enum import Enum

from .errors import InvariantViolation
from .identifiers import (
    EvidenceRecordId,
    HypothesisId,
    HypothesisRecordId,
    ParticipantId,
    SpaceId,
    StatementVersionId,
    SubjectId,
    WorldModelVersionId,
)
from .scope import DEFAULT_SPACE_ID
from .uncertainty import HypothesisSupport


class ClaimClass(Enum):
    """The bounded claim class of a commitment (Technical Design v1.5.4 §2 H)."""

    INTENTION = "intention"
    BEHAVIOUR_PATTERN = "behaviour_pattern"
    INTERPRETATION = "interpretation"
    RELATIONAL_DYNAMIC = "relational_dynamic"


class Stance(Enum):
    """The polarity of a commitment (§2 H)."""

    AFFIRMS = "affirms"
    NEGATES = "negates"
    OPEN = "open"


def inverts(a: Stance, b: Stance) -> bool:
    """Structural stance inversion (§2 H, §3.2 check 10, N-8).

    Inversion is ``affirms`` <-> ``negates`` and nothing else. ``open`` never
    inverts another stance and is never itself inverted. This is a comparison of
    two enum values and involves no semantic judgement.
    """
    return {a, b} == {Stance.AFFIRMS, Stance.NEGATES}


#: The two governed voice labels (§2 H: "participant account | Sanuvia working
#: reading"). ``attribution`` is immutable on the lineage and forms half the
#: retrieval bound, so a participant's own account and Sanuvia's working
#: reading can never merge into one lineage.
#:
#: These are constants, not free text, because the distinction is semantic: a
#: commitment the participant made and an interpretation the system formed are
#: different kinds of claim about the world, and conflating them would merge
#: them into a single lineage.
VOICE_PARTICIPANT_ACCOUNT = "participant account"
VOICE_SANUVIA_WORKING_READING = "Sanuvia working reading"

#: Every attribution an adapter may assign. An appraiser proposes
#: interpretations, so a model-proposed reading is always the working reading;
#: ``participant account`` is reserved for a commitment separately attributed
#: to the participant and is never chosen by an appraiser.
GOVERNED_VOICES: frozenset[str] = frozenset(
    {VOICE_PARTICIPANT_ACCOUNT, VOICE_SANUVIA_WORKING_READING}
)


@dataclass(frozen=True, slots=True)
class CommitmentSignature:
    """What a candidate reading commits to (§2 H).

    The split is governance-approved:

    * ``subject`` and ``attribution`` are **immutable across the lineage** — they
      are the retrieval key, and a mutable key could not prevent unsafe
      cross-attribution merging.
    * ``claim_class``, ``stance`` and ``temporal_scope`` are **versioned with the
      statement**, bounded by the R1a refinement rule.
    """

    subject: ParticipantId
    attribution: str
    claim_class: ClaimClass
    stance: Stance
    temporal_scope: str | None = None

    def __post_init__(self) -> None:
        if not self.subject:
            raise InvariantViolation("CommitmentSignature.subject must be non-empty")
        if not self.attribution:
            raise InvariantViolation("CommitmentSignature.attribution must be non-empty")

    @property
    def lineage_key(self) -> tuple[ParticipantId, str]:
        """The immutable retrieval bound (§2 H, F-2).

        ``claim_class`` is deliberately **not** part of this key: bounding
        retrieval on a versioned field would mean a candidate proposing a
        legitimate refinement failed to retrieve its own lineage.
        """
        return (self.subject, self.attribution)


@dataclass(frozen=True, slots=True)
class HypothesisLineage:
    """The immutable half of a commitment signature, written once at DISTINCT_NEW.

    A reasoning-store write (§5.1, F-9): it lives in ``HypothesisLineageStore``
    and participates in snapshot/restore like any other durable record.
    """

    hypothesis_id: HypothesisId
    subject_id: SubjectId
    space_id: SpaceId
    signature_subject: ParticipantId
    attribution: str
    created_at: datetime

    @property
    def lineage_key(self) -> tuple[ParticipantId, str]:
        return (self.signature_subject, self.attribution)


@dataclass(frozen=True, slots=True)
class StatementVersion:
    """An immutable statement version (§2 I).

    Mirrors the existing ``record_id`` / ``supersedes_record_id`` mechanism
    rather than replacing it. ``REFINE_EXISTING`` appends one of these and never
    overwrites the prior statement.
    """

    id: StatementVersionId
    hypothesis_id: HypothesisId
    statement: str
    claim_class: ClaimClass
    stance: Stance
    created_at_version: WorldModelVersionId
    temporal_scope: str | None = None
    supersedes: StatementVersionId | None = None

    def __post_init__(self) -> None:
        if not self.statement:
            raise InvariantViolation("StatementVersion.statement must be non-empty")


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
