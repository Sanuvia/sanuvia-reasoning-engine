"""Reasoning scope — the ``(space_id, subject_id)`` isolation boundary.

Finding 1 (subject / space / actor isolation) establishes three distinct
identifiers that must never be collapsed:

* ``space_id``  — *where* reasoning belongs; the isolation/access boundary.
* ``subject_id`` — *who/what* the reasoning concerns, within a space.
* ``actor_id``   — *who contributed* the evidence (recorded on ``EvidenceRecord``).

A :class:`ReasoningScope` is the composite partition key ``(space_id,
subject_id)``. All persisted reasoning state is owned by exactly one scope, and
repositories only ever return entities belonging to the requested scope.

``DEFAULT_SPACE_ID`` is the canonical space used by single-space callers (the
exit-test harness, the review harness, and legacy data migrated from before
spaces existed). It is a real, distinct constant — it is **never** derived from a
subject id, so the concepts stay separate.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .errors import InvariantViolation
from .identifiers import SpaceId, SubjectId

# The default isolation boundary for single-space operation. Distinct constant —
# not derived from any subject id.
DEFAULT_SPACE_ID: SpaceId = SpaceId("space:default")


class SpaceKind(str, Enum):
    """Whether a space is one participant's private area or a shared one.

    The reasoning engine treats every space as an opaque isolation boundary and
    is agnostic to this kind; the distinction exists so callers (and access
    control, above Phase 0) can label spaces. ``PERSONAL`` spaces hold one
    participant's private reasoning; ``SHARED`` spaces are collaborative.
    """

    PERSONAL = "personal"
    SHARED = "shared"


def personal_space_id(owner_id: str) -> SpaceId:
    """Well-formed id for a participant's *personal* space."""
    if not owner_id:
        raise InvariantViolation("personal space requires a non-empty owner id")
    return SpaceId(f"space:personal:{owner_id}")


def shared_space_id(name: str) -> SpaceId:
    """Well-formed id for a *shared* space."""
    if not name:
        raise InvariantViolation("shared space requires a non-empty name")
    return SpaceId(f"space:shared:{name}")


def space_kind_of(space_id: SpaceId) -> SpaceKind | None:
    """The kind of a well-formed space id, or ``None`` when it is not one.

    The engine treats every space as an opaque isolation boundary, so this is a
    **labelling** helper, not an access-control decision: it reads the kind the
    well-formed id already declares (``space:personal:`` / ``space:shared:``).

    ``None`` means "this id does not declare a kind", which is distinct from
    "personal". The default space is neither, and the disclosure check treats
    an undeclared kind as not shared rather than assuming either way.
    """
    text = str(space_id)
    if text.startswith("space:shared:"):
        return SpaceKind.SHARED
    if text.startswith("space:personal:"):
        return SpaceKind.PERSONAL
    return None


@dataclass(frozen=True, slots=True)
class ReasoningScope:
    """The composite ownership boundary ``(space_id, subject_id)``.

    Every piece of reasoning state belongs to exactly one scope. Two scopes that
    differ in *either* the space or the subject are fully isolated from each
    other — a subject in space A shares nothing with the same subject in space B,
    and two subjects in the same space share nothing.
    """

    space_id: SpaceId
    subject_id: SubjectId

    def __post_init__(self) -> None:
        if not self.space_id:
            raise InvariantViolation("ReasoningScope.space_id must be non-empty")
        if not self.subject_id:
            raise InvariantViolation("ReasoningScope.subject_id must be non-empty")

    @classmethod
    def for_subject(
        cls, subject_id: SubjectId, *, space_id: SpaceId = DEFAULT_SPACE_ID
    ) -> "ReasoningScope":
        """Build a scope for a subject, defaulting to the single default space."""
        return cls(space_id=space_id, subject_id=subject_id)
