"""Validation and completion of extractor-proposed evidence standing (§2 E, R2).

The division R2 authorises, enforced here:

* the **extractor proposes** the parts that cannot be supplied from context --
  ``role``, ``subject`` and ``subject_kind``;
* the **application supplies** the contextual facts -- the speaking
  participant, and therefore ``source_kind`` and ``source_id``. These are never
  asked of the model and never accepted from it;
* the **application validates** the proposal. A proposed ``role`` or
  ``subject`` outside the permitted enum or identifier set is a governed
  failure, not a value to repair.

Ruling Q6, applied exactly: an invalid proposal rejects the **whole
interaction**. The complete extraction output is preserved, the rejection is
``EVIDENCE_ROLE_VIOLATION``, nothing is committed to reasoning state, no repair
or normalisation is performed, and **no segment-level partial commit occurs**.
"""

from __future__ import annotations

from collections.abc import Sequence

from sanuvia.domain import (
    EvidenceRole,
    EvidenceSourceKind,
    EvidenceStanding,
    EvidenceSubjectKind,
    GovernedOutcome,
    GovernedRejection,
    ParticipantId,
)

from .extraction import ProposedStanding

_ROLES = {role.value: role for role in EvidenceRole}
_SUBJECT_KINDS = {kind.value: kind for kind in EvidenceSubjectKind}


def _reject(detail: str, ref: str) -> GovernedRejection:
    return GovernedRejection(
        GovernedOutcome.EVIDENCE_ROLE_VIOLATION,
        f"extractor-proposed standing for observation {ref!r} is invalid: {detail}",
        references=(ref,),
    )


def complete_standing(
    proposed: ProposedStanding | None,
    *,
    ref: str,
    speaker: str | None,
    permitted_participants: Sequence[str],
) -> EvidenceStanding | None:
    """Validate a proposal and complete it with the contextual facts.

    Returns ``None`` when the extractor proposed nothing. That is deliberate:
    absent standing is left absent rather than defaulted to ordinary supporting
    evidence, because defaulting is exactly how a ``RESPONSE_OR_RESONANCE``
    turn would silently acquire the power to raise support.
    """
    if proposed is None:
        return None

    role = _ROLES.get(proposed.role)
    if role is None:
        raise _reject(
            f"role {proposed.role!r} is not one of {sorted(_ROLES)}", ref
        )

    subject_kind = _SUBJECT_KINDS.get(proposed.subject_kind)
    if subject_kind is None:
        raise _reject(
            f"subject_kind {proposed.subject_kind!r} is not one of "
            f"{sorted(_SUBJECT_KINDS)}",
            ref,
        )

    permitted = set(permitted_participants)
    needs_subject = subject_kind in (
        EvidenceSubjectKind.PARTICIPANT,
        EvidenceSubjectKind.THIRD_PARTY,
    )
    if needs_subject:
        if proposed.subject is None:
            raise _reject(
                f"subject_kind {subject_kind.value} requires a subject", ref
            )
        if proposed.subject not in permitted:
            raise _reject(
                f"subject {proposed.subject!r} is not a permitted participant "
                f"identifier",
                ref,
            )
    elif proposed.subject is not None and proposed.subject not in permitted:
        raise _reject(
            f"subject {proposed.subject!r} is not a permitted participant "
            f"identifier",
            ref,
        )

    # Contextual half, supplied by the application. A turn with a recorded
    # speaker is a participant source; without one it is a system surface.
    if speaker is not None:
        if speaker not in permitted:
            raise _reject(
                f"speaker {speaker!r} is not a permitted participant identifier",
                ref,
            )
        source_kind = EvidenceSourceKind.PARTICIPANT
        source_id = ParticipantId(speaker)
    else:
        source_kind = EvidenceSourceKind.SYSTEM_SURFACE
        source_id = None

    return EvidenceStanding(
        source_kind=source_kind,
        subject_kind=subject_kind,
        role=role,
        source_id=source_id,
        subject_id=(
            ParticipantId(proposed.subject) if proposed.subject is not None else None
        ),
    )
