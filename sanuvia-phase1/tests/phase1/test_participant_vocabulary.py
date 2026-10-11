"""Request-scoped participant vocabulary at the extraction boundary (§2 B, §2 E).

The rule these assert: a model-supplied string may become a canonical
``ParticipantId`` only by having been offered as a label for *that request*.
Everything else -- an unoffered label, a canonical id, a label from another
interaction, a name lifted out of the text -- is a governed failure under ruling
Q6, which rejects the whole interaction.

Fake clients only. No provider is selected and nothing reaches a network.
"""

from __future__ import annotations

import json

import pytest

from sanuvia.domain import (
    EvidenceSourceKind,
    EvidenceSubjectKind,
    GovernedOutcome,
    GovernedRejection,
)

from sanuvia_phase1.evidence_extractors.external import ExternalEvidenceExtractor
from sanuvia_phase1.extraction import ExtractedEvidence
from sanuvia_phase1.participants import (
    PREFIX,
    SEP,
    ParticipantVocabulary,
    build_participant_vocabulary,
)
from sanuvia_phase1.transcript import TranscriptInteraction

ROSTER = ("pB", "pA")  # deliberately unsorted: minting sorts.


# --- the vocabulary itself ---------------------------------------------------


def test_labels_are_request_scoped_and_minted_over_the_sorted_roster() -> None:
    """The scheme is the one ``handles.build_table`` already fixes for the
    appraisal boundary -- ``{request_id}::P{n}`` over sorted participants --
    not a second scheme invented for extraction."""
    vocabulary = build_participant_vocabulary("t-1:3", ROSTER)

    assert vocabulary.labels == (f"t-1:3{SEP}{PREFIX}1", f"t-1:3{SEP}{PREFIX}2")
    assert vocabulary.participants == ("pA", "pB")  # sorted, deduplicated


def test_the_same_roster_always_mints_the_same_labels() -> None:
    """Replay determinism: a repeated request is byte-identical."""
    first = build_participant_vocabulary("t-1:1", ROSTER)
    second = build_participant_vocabulary("t-1:1", ("pA", "pB", "pA"))

    assert first == second


def test_different_requests_mint_different_labels_for_one_participant() -> None:
    """Request-scoped means the request id is part of the label, so a label
    from another interaction fails resolution rather than aliasing silently."""
    one = build_participant_vocabulary("t-1:1", ROSTER)
    two = build_participant_vocabulary("t-1:2", ROSTER)

    assert one.label_for("pA") != two.label_for("pA")


def test_resolution_maps_a_label_back_to_the_canonical_id() -> None:
    vocabulary = build_participant_vocabulary("t-1:1", ROSTER)
    label = vocabulary.label_for("pB")
    assert label is not None

    assert vocabulary.resolve(label, ref="r", field="subject") == "pB"


def test_an_unoffered_label_is_refused_not_resolved() -> None:
    vocabulary = build_participant_vocabulary("t-1:1", ROSTER)

    with pytest.raises(GovernedRejection) as exc:
        vocabulary.resolve("t-1:1::P9", ref="r", field="subject")

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION
    assert "was not supplied in request" in str(exc.value)


def test_an_empty_vocabulary_offers_nothing_and_resolves_nothing() -> None:
    """Empty is a real state -- a GOLDEN run has no roster -- and it refuses
    everything rather than resolving by accident."""
    vocabulary = ParticipantVocabulary(request_id="t-1:1")

    assert not vocabulary
    assert vocabulary.labels == ()
    with pytest.raises(GovernedRejection):
        vocabulary.resolve("anything", ref="r", field="subject")


# --- the vocabulary through the real extractor -------------------------------


def _reply(subject: object) -> str:
    return json.dumps(
        {
            "evidence": [
                {
                    "observation": "the partner left the room",
                    "evidence_class": "behavioural",
                    "reliability": 0.8,
                    "classification_confidence": 0.9,
                    "provenance_confidence": 0.9,
                    "text_span": None,
                    "role": "account",
                    "subject_kind": "participant",
                    "subject": subject,
                }
            ]
        }
    )


def _extract(
    subject: object, *, speaker: str | None = "pA"
) -> tuple[ExtractedEvidence, ...]:
    extractor = ExternalEvidenceExtractor(
        client=lambda _r: _reply(subject), permitted_participants=ROSTER
    )
    return extractor.extract(
        TranscriptInteraction(1, "seq-1", "she left the room", speaker=speaker), "t-1"
    )


def _label_for(participant: str, *, index: int = 1) -> str:
    label = build_participant_vocabulary(f"t-1:{index}", ROSTER).label_for(participant)
    assert label is not None
    return label


def test_a_valid_label_maps_to_the_canonical_participant() -> None:
    """The whole inbound contract in one assertion."""
    (evidence,) = _extract(_label_for("pB"))

    assert evidence.standing is not None
    assert evidence.standing.subject_id == "pB"
    assert evidence.standing.subject_kind is EvidenceSubjectKind.PARTICIPANT


def test_an_unknown_label_rejects_the_interaction() -> None:
    with pytest.raises(GovernedRejection) as exc:
        _extract("t-1:1::P7")

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


def test_a_canonical_identifier_rejects_the_interaction() -> None:
    """``pB`` is authorized. It is still refused: the model was not given it,
    and the application must never infer that a model-supplied string is a
    canonical reference."""
    with pytest.raises(GovernedRejection) as exc:
        _extract("pB")

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


def test_a_label_from_a_different_interaction_rejects() -> None:
    with pytest.raises(GovernedRejection) as exc:
        _extract(_label_for("pB", index=2))

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


def test_a_name_taken_from_the_text_rejects() -> None:
    """The model may not promote a name it read into a participant identity."""
    with pytest.raises(GovernedRejection) as exc:
        _extract("the partner")

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


@pytest.mark.parametrize("malformed", [42, [], {}, True])
def test_a_malformed_subject_is_a_shape_failure_at_the_validator(
    malformed: object,
) -> None:
    """A non-string subject never reaches the vocabulary: the strict reader
    refuses the shape first, and it is not coerced to a label."""
    from sanuvia_phase1.failures import MalformedOutputError

    with pytest.raises((MalformedOutputError, GovernedRejection)):
        _extract(malformed)


def test_rejection_preserves_the_raw_response_and_provenance() -> None:
    """Q6: the complete extraction output survives on the rejection, so the
    audit shows what the extractor actually returned."""
    with pytest.raises(GovernedRejection) as exc:
        _extract("pB")

    assert exc.value.raw_response is not None
    assert "pB" in exc.value.raw_response
    assert ("extractor_id", "external-extractor") in exc.value.provenance


def test_the_outbound_prompt_carries_labels_and_no_canonical_id() -> None:
    seen: list[object] = []

    def _client(request: object) -> str:
        seen.append(request)
        return _reply(_label_for("pB"))

    ExternalEvidenceExtractor(
        client=_client, permitted_participants=ROSTER
    ).extract(TranscriptInteraction(1, "seq-1", "text", speaker="pA"), "t-1")

    (request,) = seen
    assert request.participants == (  # type: ignore[attr-defined]
        _label_for("pA"),
        _label_for("pB"),
    )


def test_a_dyad_subject_needs_no_label_and_mints_no_participant() -> None:
    """``subject`` is null for dyad/none, and nothing is invented to fill it."""
    reply = json.dumps(
        {
            "evidence": [
                {
                    "observation": "they stopped speaking",
                    "evidence_class": "behavioural",
                    "reliability": 0.8,
                    "classification_confidence": 0.9,
                    "provenance_confidence": 0.9,
                    "text_span": None,
                    "role": "event_observation",
                    "subject_kind": "dyad",
                    "subject": None,
                }
            ]
        }
    )
    extractor = ExternalEvidenceExtractor(
        client=lambda _r: reply, permitted_participants=ROSTER
    )
    (evidence,) = extractor.extract(
        TranscriptInteraction(1, "seq-1", "text", speaker="pA"), "t-1"
    )

    assert evidence.standing is not None
    assert evidence.standing.subject_id is None
    assert evidence.standing.source_kind is EvidenceSourceKind.PARTICIPANT
