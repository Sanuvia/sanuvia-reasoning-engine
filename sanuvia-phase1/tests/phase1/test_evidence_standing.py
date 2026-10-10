"""Extractor-supplied evidence standing (§2 E, R2) and the live role gate.

The division R2 authorises:

* the extractor PROPOSES ``role``, ``subject`` and ``subject_kind`` -- the
  parts that cannot be supplied from context;
* the application SUPPLIES the contextual facts: who spoke, and therefore
  ``source_kind`` / ``source_id``, plus the permitted participant set;
* the application VALIDATES the proposal, and an invalid one rejects the whole
  interaction under ruling Q6.

The point of all of it: ``RESPONSE_OR_RESONANCE`` must not be able to raise
support. Before this, Phase 1 extraction supplied no standing at all, so the
gate could never fire on the real path.

Fake clients only. No model inference.
"""

from __future__ import annotations

from sanuvia.application.ports.reasoning import AppraisalRequest, AppraisalResponse

from typing import Any

import json

import pytest

from sanuvia.domain import (
    APPRAISABLE_ROLES,
    EvidenceRole,
    EvidenceSourceKind,
    EvidenceSubjectKind,
    GovernedOutcome,
    GovernedRejection,
)

from sanuvia_phase1.evidence_extractors.external import ExternalEvidenceExtractor
from sanuvia_phase1.failures import MalformedOutputError
from sanuvia_phase1.transcript import TranscriptInteraction

PERMITTED = ("pA", "pB")


def _reply(role: str | None = "event_observation", *, subject_kind: str = "participant",
           subject: str | None = "pB", omit_standing: bool = False,
           extra: dict[str, object] | None = None) -> str:
    item = {
        "observation": "the partner left the room",
        "evidence_class": "behavioural",
        "reliability": 0.8,
        "classification_confidence": 0.9,
        "provenance_confidence": 0.9,
        "text_span": None,
    }
    if not omit_standing:
        item.update({"role": role, "subject_kind": subject_kind, "subject": subject})
    if extra:
        item.update(extra)
    return json.dumps({"evidence": [item]})


def _extract(reply: str, *, speaker: str | None = "pA") -> tuple[Any, ...]:
    extractor = ExternalEvidenceExtractor(
        client=lambda _r: reply, permitted_participants=PERMITTED
    )
    interaction = TranscriptInteraction(
        index=1, seq_label="seq-1", text="she left the room", speaker=speaker
    )
    return extractor.extract(interaction, "t-1")


# --- 1/2. the extractor supplies standing and it is persisted ----------------


def test_extractor_supplied_standing_is_completed_and_carried() -> None:
    (evidence,) = _extract(_reply("event_observation"))

    assert evidence.standing is not None
    assert evidence.standing.role is EvidenceRole.EVENT_OBSERVATION
    assert evidence.standing.subject_kind is EvidenceSubjectKind.PARTICIPANT
    assert evidence.standing.subject_id == "pB"


def test_the_application_supplies_the_speaking_participant_not_the_model() -> None:
    """source_kind/source_id are contextual facts, never asked of the model."""
    (evidence,) = _extract(_reply(), speaker="pA")

    assert evidence.standing.source_kind is EvidenceSourceKind.PARTICIPANT
    assert evidence.standing.source_id == "pA"


def test_a_model_supplied_source_is_rejected() -> None:
    """The model may not state who spoke."""
    with pytest.raises(MalformedOutputError, match="source_kind"):
        _extract(_reply(extra={"source_kind": "participant", "source_id": "pB"}))


def test_standing_reaches_the_engine_through_the_evidence_input() -> None:
    """The gate is only live if the standing actually arrives."""
    from fixtures.longitudinal.case_001 import CASE_001
    from sanuvia_phase1.case import CaseEvidence

    assert "standing" in CaseEvidence.__dataclass_fields__
    # And the Case builds EvidenceInput with it.
    import inspect

    from sanuvia_phase1 import case as case_module

    assert "standing=ev.standing" in inspect.getsource(case_module.Case.evidence_inputs)


# --- 3. the application validates, it does not trust -------------------------


@pytest.mark.parametrize("bad_role", ["resonance", "EVENT_OBSERVATION", "unknown"])
def test_an_invalid_proposed_role_rejects_the_whole_interaction(bad_role: str) -> None:
    """Q6: governed failure, no repair, no partial commit.

    This previously accepted either exception class. A non-empty but
    unpermitted role is a VALUE the application judges, so the governed outcome
    is required; the empty-string case is a shape failure the validator catches
    first and is asserted separately below.
    """
    with pytest.raises(GovernedRejection) as exc:
        _extract(_reply(bad_role))

    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION
    # Q6: the complete extraction output is preserved on the rejection.
    assert exc.value.raw_response is not None
    assert bad_role in exc.value.raw_response


def test_an_empty_role_is_a_shape_failure_at_the_validator() -> None:
    """An absent value never reaches the application's value judgement."""
    with pytest.raises(MalformedOutputError, match="role"):
        _extract(_reply(""))


def test_an_invalid_subject_kind_rejects_the_interaction() -> None:
    with pytest.raises(GovernedRejection) as exc:
        _extract(_reply(subject_kind="everyone"))
    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


def test_a_subject_outside_the_permitted_set_rejects_the_interaction() -> None:
    """The permitted identifier set is the application's, not the model's."""
    with pytest.raises(GovernedRejection) as exc:
        _extract(_reply(subject="pZ"))
    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION
    assert "permitted participant" in str(exc.value)


def test_a_participant_subject_kind_without_a_subject_is_rejected() -> None:
    with pytest.raises(GovernedRejection):
        _extract(_reply(subject=None))


def test_an_unpermitted_speaker_rejects_the_interaction() -> None:
    with pytest.raises(GovernedRejection) as exc:
        _extract(_reply(), speaker="pZ")
    assert exc.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


# --- 4. RESPONSE_OR_RESONANCE cannot become ordinary support -----------------


def test_response_or_resonance_is_not_appraisable() -> None:
    """F-1 / TD-13e: resonance cannot raise support. The whole point."""
    (evidence,) = _extract(_reply("response_or_resonance"))

    assert evidence.standing.role is EvidenceRole.RESPONSE_OR_RESONANCE
    assert evidence.standing.is_appraisable is False
    assert EvidenceRole.RESPONSE_OR_RESONANCE not in APPRAISABLE_ROLES


def test_meta_instruction_is_not_appraisable() -> None:
    (evidence,) = _extract(_reply("meta_instruction", subject_kind="none", subject=None))
    assert evidence.standing.is_appraisable is False


def test_a_non_appraisable_record_reaches_the_engine_but_is_never_appraised() -> None:
    """Q1 is structural: the engine makes no appraisal call for it at all."""
    from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
    from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
    from sanuvia.adapters.wiring import build_in_memory_dependencies
    from sanuvia.application.api.service import EvidenceInput, ReasoningService
    from sanuvia.domain import EvidenceClass, EvidenceStanding

    class _WouldPropose:
        def __init__(self) -> None:
            self.calls = 0

        def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
            self.calls += 1
            raise AssertionError("a non-appraisable record must not be appraised")

    appraiser = _WouldPropose()
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store, appraiser=appraiser,
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    standing = EvidenceStanding(
        source_kind=EvidenceSourceKind.PARTICIPANT,
        subject_kind=EvidenceSubjectKind.PARTICIPANT,
        role=EvidenceRole.RESPONSE_OR_RESONANCE,
        source_id="pA", subject_id="pB",
    )
    ReasoningService(deps).record_interaction("subject-standing", [
        EvidenceInput(
            subject_id="subject-standing", evidence_class=EvidenceClass.NARRATIVE,
            content="that resonates", source="extractor:test", reliability=0.8,
            classification_confidence=0.9, standing=standing,
        )
    ])

    assert appraiser.calls == 0, "no appraisal call was made"
    # Admitted and preserved, but it changed no support.
    assert len(store.evidence.list_for_subject("subject-standing")) == 1
    assert store.hypotheses.list_for_subject("subject-standing") == []


# --- 5. authorised roles remain appraisable ----------------------------------


@pytest.mark.parametrize("role", ["event_observation", "account"])
def test_authorised_roles_remain_appraisable(role: str) -> None:
    (evidence,) = _extract(_reply(role))
    assert evidence.standing.is_appraisable is True


# --- 6. absent standing is left absent ---------------------------------------


def test_absent_standing_is_not_defaulted_to_ordinary_support() -> None:
    """Do not invent standing. Absent means absent, not 'ordinary evidence'."""
    (evidence,) = _extract(_reply(omit_standing=True))
    assert evidence.standing is None


# --- 7. standing changes neither attribution nor identity --------------------


def test_standing_does_not_change_attribution_or_identity_semantics() -> None:
    """Standing is about what an observation IS, not whose commitment it states."""
    observation_role = _extract(_reply("event_observation"))[0]
    account_role = _extract(_reply("account"))[0]

    # Different standing, identical everything the identity path reads.
    assert observation_role.standing.role is not account_role.standing.role
    assert observation_role.observation == account_role.observation
    assert observation_role.reliability == account_role.reliability
    # EvidenceStanding carries no attribution and no hypothesis identity.
    fields = set(type(observation_role.standing).__dataclass_fields__)
    assert "attribution" not in fields
    assert "hypothesis_id" not in fields
