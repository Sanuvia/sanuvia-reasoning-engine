"""Governed speaker context (§2 E, §2 J.1).

Who spoke is a CONTEXTUAL fact. The application supplies it from the transcript
and the authorized roster; it is never asked of the model, never accepted from
the model, and -- the part these tests exist for -- never *inferred* when the
context does not establish one.

A speakerless turn is therefore not a failure and not a guess. It stands as
``SYSTEM_SURFACE``, which ``EvidenceStanding.is_participant_account`` reads as
false, so such a record is neither a divergence endpoint nor a divergence
candidate (§2 J.1 rules 2-3). That consequence is asserted end to end through
the frozen engine, not merely on the standing object, because the standing being
right is only useful if the engine's candidate set follows it.

Fake clients only. No provider is selected and nothing reaches a network.
"""

from __future__ import annotations

import json

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import AppraisalRequest, AppraisalResponse
from sanuvia.domain import (
    EvidenceClass,
    EvidenceRole,
    EvidenceSourceKind,
    EvidenceStanding,
    EvidenceSubjectKind,
    GovernedOutcome,
    GovernedRejection,
    shared_space_id,
)

from sanuvia_phase1.evidence_extractors.external import ExternalEvidenceExtractor
from sanuvia_phase1.extraction import ExtractedEvidence
from sanuvia_phase1.participants import build_participant_vocabulary
from sanuvia_phase1.transcript import TranscriptInteraction

ROSTER = ("pA", "pB")
SUBJECT = "subject-speaker"
SPACE = shared_space_id("dyad-1")


def _standing_of(evidence: ExtractedEvidence) -> EvidenceStanding:
    """Narrow the optional. Standing being present is itself the claim, so a
    missing one must fail here rather than be skipped over."""
    assert evidence.standing is not None
    return evidence.standing


def _label(participant: str, *, index: int = 1) -> str:
    label = build_participant_vocabulary(f"t-1:{index}", ROSTER).label_for(participant)
    assert label is not None
    return label


def _reply(role: str = "account", *, index: int = 1) -> str:
    return json.dumps(
        {
            "evidence": [
                {
                    "observation": "the evening ended badly",
                    "evidence_class": "narrative",
                    "reliability": 0.8,
                    "classification_confidence": 0.9,
                    "provenance_confidence": 0.9,
                    "text_span": None,
                    "role": role,
                    "subject_kind": "participant",
                    "subject": _label("pB", index=index),
                }
            ]
        }
    )


def _extract(
    *, speaker: str | None, role: str = "account", index: int = 1
) -> tuple[ExtractedEvidence, ...]:
    extractor = ExternalEvidenceExtractor(
        client=lambda _r: _reply(role, index=index), permitted_participants=ROSTER
    )
    return extractor.extract(
        TranscriptInteraction(index, f"seq-{index}", "it ended badly", speaker=speaker),
        "t-1",
    )


# --- 1. a known speaker ------------------------------------------------------


def test_a_known_speaker_becomes_the_participant_source() -> None:
    (evidence,) = _extract(speaker="pA")

    assert _standing_of(evidence).source_kind is EvidenceSourceKind.PARTICIPANT
    assert _standing_of(evidence).source_id == "pA"
    assert _standing_of(evidence).is_participant_account is True


def test_the_speaker_is_supplied_as_a_canonical_id_not_a_label() -> None:
    """The asymmetry is deliberate: the subject arrives from the model as a
    label and is resolved; the speaker arrives from the application already
    canonical and is only checked for membership."""
    (evidence,) = _extract(speaker="pA")

    assert _standing_of(evidence).source_id == "pA"
    assert _standing_of(evidence).source_id != _label("pA")


# --- 2. an invalid speaker reference ----------------------------------------


def test_an_unauthorised_speaker_rejects_the_interaction() -> None:
    with pytest.raises(GovernedRejection) as exc:
        _extract(speaker="pZ")

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION
    assert "not a permitted participant" in str(exc.value)


def test_a_speaker_given_as_a_label_is_refused() -> None:
    """A label is not a canonical id. Accepting one here would let the two
    namespaces blur, which is how a resolved subject could later be mistaken
    for a speaker."""
    with pytest.raises(GovernedRejection) as exc:
        _extract(speaker=_label("pA"))

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


# --- 3. a speakerless turn ---------------------------------------------------


@pytest.mark.parametrize("role", ["account", "event_observation"])
def test_a_speakerless_turn_is_a_system_surface(role: str) -> None:
    """Every applicable extracted record, not merely the first."""
    (evidence,) = _extract(speaker=None, role=role)

    assert _standing_of(evidence).source_kind is EvidenceSourceKind.SYSTEM_SURFACE
    assert _standing_of(evidence).source_id is None


def test_no_speaker_is_inferred_from_the_roster() -> None:
    """A two-person roster does not make either of them the speaker."""
    (evidence,) = _extract(speaker=None)

    assert _standing_of(evidence).source_id is None
    assert _standing_of(evidence).source_id not in ROSTER


def test_no_speaker_is_inferred_from_the_subject() -> None:
    """The observation is ABOUT pB. That does not make anyone the speaker."""
    (evidence,) = _extract(speaker=None)

    assert _standing_of(evidence).subject_id == "pB"
    assert _standing_of(evidence).source_id is None


def test_a_speakerless_account_is_not_a_participant_account() -> None:
    """The bridge to divergence: rules 2-3 key on exactly this predicate."""
    (evidence,) = _extract(speaker=None, role="account")

    assert _standing_of(evidence).role is EvidenceRole.ACCOUNT
    assert _standing_of(evidence).is_participant_account is False


# --- 4. divergence eligibility, through the frozen engine --------------------


class _CapturesCandidates:
    """Records the divergence candidates the engine actually offered."""

    def __init__(self) -> None:
        self.offered: list[tuple[str, ...]] = []

    def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
        self.offered.append(
            tuple(str(c.handle) for c in request.divergence_candidates)
        )
        return AppraisalResponse()


def _standing(source_id: str | None) -> EvidenceStanding:
    return EvidenceStanding(
        source_kind=(
            EvidenceSourceKind.SYSTEM_SURFACE
            if source_id is None
            else EvidenceSourceKind.PARTICIPANT
        ),
        subject_kind=EvidenceSubjectKind.PARTICIPANT,
        role=EvidenceRole.ACCOUNT,
        source_id=source_id,
        subject_id="pB",
    )


def _run(*source_ids: str | None) -> _CapturesCandidates:
    """Ingest one account per source, one interaction each, same subject+space."""
    appraiser = _CapturesCandidates()
    deps = build_in_memory_dependencies(
        store=InMemoryReasoningStore(),
        appraiser=appraiser,
        ids=SequentialIdGenerator(),
        clock=ManualClock(),
    )
    service = ReasoningService(deps)
    for n, source_id in enumerate(source_ids, start=1):
        service.record_interaction(
            SUBJECT,
            [
                EvidenceInput(
                    subject_id=SUBJECT,
                    evidence_class=EvidenceClass.NARRATIVE,
                    content=f"account {n}",
                    source="extractor:test",
                    reliability=0.8,
                    classification_confidence=0.9,
                    standing=_standing(source_id),
                )
            ],
            space_id=SPACE,
        )
    return appraiser


def test_speakerless_records_offer_an_empty_divergence_candidate_set() -> None:
    """The defining assertion of requirement 3.

    Two accounts about the same subject in one shared space -- the shape that
    normally produces a divergence candidate. With no speaker on either, the
    engine offers nothing, because neither record is a participant account.
    """
    appraiser = _run(None, None)

    assert appraiser.offered == [(), ()]


def test_the_control_confirms_the_set_is_otherwise_non_empty() -> None:
    """Without this, the test above could pass because divergence never fires.

    Same subject, same space, same role -- two DIFFERENT speakers. The second
    appraisal is offered the first record as a divergence candidate, so the
    empty set above is caused by the missing speaker and nothing else.
    """
    appraiser = _run("pA", "pB")

    assert appraiser.offered[0] == ()  # nothing committed yet to diverge from
    assert len(appraiser.offered[1]) == 1


def test_a_speakerless_record_is_not_offered_to_a_later_speaking_one() -> None:
    """Eligibility is a property of BOTH endpoints (rules 2 and 3)."""
    appraiser = _run(None, "pA")

    assert appraiser.offered == [(), ()]


def test_a_speaking_record_is_not_offered_to_a_later_speakerless_one() -> None:
    appraiser = _run("pA", None)

    assert appraiser.offered == [(), ()]
