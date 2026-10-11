"""Request-scoped participant labels for the extraction boundary (§2 B, §2 E).

Why this exists
---------------

The extraction boundary previously asked the model for a ``subject`` as a bare
string and then checked it against the authorized participant set. That makes
the model's reply a *durable participant identifier* whenever it happens to
match, which is the thing locked §3.1 prohibits: the application must never
infer that a model-supplied string is a canonical reference. It was refused
only when no participant happened to be called that -- a membership accident,
not a rule.

Phase 0 already solved this for the appraisal boundary. ``handles.build_table``
mints ``{request_id}::P{n}`` over the sorted participants and
``HandleTable.resolve_participant`` refuses any label it did not supply, so a
model that cannot see a ``ParticipantId`` cannot assign one. The identity
resolver mints ``C1``, ``C2`` for the same reason.

This module applies that established scheme to extraction. It introduces no new
contract: the label format, the sort order and the refusal are the ones
``handles.py`` already fixes.

What crosses the boundary
-------------------------

Outbound: the labels for this request, and nothing else. No ``ParticipantId``,
no ``SubjectId``, no ``HypothesisId``.

Inbound: a label. It is resolved back to the canonical ``ParticipantId``
**inside the application boundary**, here. A label this request did not offer is
a governed failure under ruling Q6 -- it rejects the whole interaction, is not
repaired, and is never carried forward as though it were a participant.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sanuvia.domain import GovernedOutcome, GovernedRejection

#: The request/label separator. Identical to ``handles._SEP`` by intent: the two
#: boundaries mint labels under one scheme, so a reviewer reading a transcript
#: and an appraisal prompt sees the same shape and the same guarantee.
SEP = "::"

#: The label prefix, as ``handles.build_table`` uses for participants.
PREFIX = "P"


@dataclass(frozen=True, slots=True)
class ParticipantVocabulary:
    """The closed set of participant labels one extraction request may use.

    ``entries`` is ``(label, participant_id)`` in label order. Empty is a
    legitimate state only for a GOLDEN run or a request with no authorized
    participants; REAL-mode configuration refuses it up front
    (``runconfig.validate_run_configuration``) rather than letting every
    extracted subject be rejected one at a time.
    """

    request_id: str
    entries: tuple[tuple[str, str], ...] = ()

    @property
    def labels(self) -> tuple[str, ...]:
        """The labels to send. This is the whole outbound vocabulary."""
        return tuple(label for label, _ in self.entries)

    @property
    def participants(self) -> tuple[str, ...]:
        """The canonical participant ids. Never sent to the model."""
        return tuple(participant for _, participant in self.entries)

    def __bool__(self) -> bool:
        return bool(self.entries)

    def label_for(self, participant_id: str) -> str | None:
        """The label standing for a canonical id, or ``None`` if unauthorized.

        Used to project a contextual fact the application already knows (the
        speaker) into label space for the prompt. It never travels inbound.
        """
        for label, participant in self.entries:
            if participant == participant_id:
                return label
        return None

    def resolve(self, label: str, *, ref: str, field: str) -> str:
        """Map a model-returned label back to its canonical participant id.

        A label this request did not offer is refused, not resolved. This is the
        single point at which a model-supplied string may become a canonical
        reference, and it may only do so by having been offered first.
        """
        for offered, participant in self.entries:
            if offered == label:
                return participant
        raise GovernedRejection(
            GovernedOutcome.EVIDENCE_ROLE_VIOLATION,
            f"extractor-proposed standing for observation {ref!r} is invalid: "
            f"{field} {label!r} was not supplied in request "
            f"{self.request_id!r}; the offered participant labels are "
            f"{list(self.labels)}",
            references=(ref,),
        )


def build_participant_vocabulary(
    request_id: str, authorized: Sequence[str]
) -> ParticipantVocabulary:
    """Mint the labels for one request over its authorized participants.

    Sorted and deduplicated before minting, exactly as
    ``handles.build_table`` does, so the same roster always yields the same
    labels and a replayed request is byte-identical.
    """
    return ParticipantVocabulary(
        request_id=request_id,
        entries=tuple(
            (f"{request_id}{SEP}{PREFIX}{i}", participant)
            for i, participant in enumerate(sorted(set(authorized)), start=1)
        ),
    )
