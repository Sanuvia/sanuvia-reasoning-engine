"""Slice 2 blocker regressions (independent review, 2026-10-07).

Each exercises the real caller path and asserts the governed audit record and
the rollback, not merely that an exception was raised.

Fake clients only. No provider, no network, no model inference.
"""

from __future__ import annotations

import json

import pytest

from fixtures.longitudinal.case_001 import CASE_001

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import (
    AppraisalResponse,
    CandidateProposal,
    CommitmentSignatureView,
)
from sanuvia.application.reasoning.unit_of_work import bundle_stores
from sanuvia.domain import (
    VOICE_SANUVIA_WORKING_READING,
    ClaimClass,
    EvidenceClass,
    GovernedOutcome,
    GovernedRejection,
    ModelBoundary,
    Stance,
    SubjectId,
    shared_space_id,
)

from sanuvia_phase1.capture import from_rejected_plan
from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.evidence_extractors.external import ExternalEvidenceExtractor
from sanuvia_phase1.identity_resolvers import RESOLVER_ID, ExternalIdentityResolver
from sanuvia_phase1.identity_resolvers.external import PROMPT_VERSION, SCHEMA_VERSION
from sanuvia_phase1.trajectory import InteractionOutcome
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction
from sanuvia_phase1 import pipeline

SUBJECT = "subject-blockers"


# ===========================================================================
# B-1 / B-2 — resolver closed vocabulary and governed rejection
# ===========================================================================


def _ev(text: str) -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE, content=text,
        source="extractor:test", reliability=0.8, classification_confidence=0.9,
    )


class _ProposesTwoReadings:
    """Founds a lineage, then proposes a non-exact reading under the same bound."""

    def __init__(self) -> None:
        self.calls = 0

    def appraise(self, request):
        self.calls += 1
        statement = "the first reading" if self.calls == 1 else "a second reading"
        signature = CommitmentSignatureView(
            subject=request.participants[0] if request.participants else "p1",
            attribution=VOICE_SANUVIA_WORKING_READING,
            claim_class=ClaimClass.INTERPRETATION, stance=Stance.OPEN,
        )
        return AppraisalResponse(
            proposals=(CandidateProposal(f"c{self.calls}", statement, signature),)
        )


def _reply(ref: str | None) -> str:
    return json.dumps({
        "outcome": "match_existing", "matched_ref": ref,
        "rationale": "same commitment", "confidence": 0.7,
    })


def _run(resolver_reply: str):
    """Two interactions through the real service with the real resolver."""
    store = InMemoryReasoningStore()
    ids = SequentialIdGenerator()
    deps = build_in_memory_dependencies(
        store=store, appraiser=_ProposesTwoReadings(), ids=ids, clock=ManualClock(),
        identity_resolver=ExternalIdentityResolver(client=lambda _p: resolver_reply),
    )
    service = ReasoningService(deps)
    service.record_interaction(SUBJECT, [_ev("first")])  # founds hyp-1
    return service, store, ids


# --- B-1 Case A: an unoffered, durable-looking reference ---------------------


def test_b1_unoffered_durable_looking_reference_is_rejected():
    """The request offered only C1; "hyp-1" is not in the vocabulary.

    It was previously carried forward AS the durable id and accepted, because
    a lineage happened to be called hyp-1. Membership in the store is not the
    rule -- the offered reference set is.
    """
    service, store, _ = _run(_reply("hyp-1"))
    assert [l.hypothesis_id for l in store.lineages.list_for_subject(SUBJECT)] == [
        "hyp-1"
    ], "the durable lineage really is called hyp-1, so this is not a near miss"

    with pytest.raises(GovernedRejection) as exc:
        service.record_interaction(SUBJECT, [_ev("second")])

    assert exc.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert exc.value.boundary is ModelBoundary.IDENTITY_RESOLVER
    assert exc.value.raw_response == _reply("hyp-1")
    assert "was not offered" in str(exc.value)


def test_b1_rejection_rolls_the_interaction_back_completely():
    service, store, ids = _run(_reply("hyp-1"))
    before_evidence = len(store.evidence.list_for_subject(SUBJECT))

    with pytest.raises(GovernedRejection):
        service.record_interaction(SUBJECT, [_ev("second")])

    # No new evidence, lineage, hypothesis or statement version.
    assert len(store.evidence.list_for_subject(SUBJECT)) == before_evidence
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    assert len(store.hypotheses.list_for_subject(SUBJECT)) == 1
    assert len(list(store.statement_versions.history("hyp-1"))) == 1

    # The existing lineage is still supported only by its original evidence.
    (hypothesis,) = store.hypotheses.list_for_subject(SUBJECT)
    assert hypothesis.supporting_evidence_ids == ("evidence-1",)

    # Identifier counters restored: the rejected interaction consumed none.
    assert ids.new_id("evidence") == "evidence-2"
    assert ids.new_id("req") == "req-2"


@pytest.mark.parametrize("unoffered", ["hyp-1", "hyp-9", "C2", "", "  "])
def test_b1_no_unoffered_reference_is_ever_accepted(unoffered):
    """Only C1 was offered, so every one of these is unusable output."""
    service, _, _ = _run(_reply(unoffered))
    with pytest.raises(GovernedRejection) as exc:
        service.record_interaction(SUBJECT, [_ev("second")])
    assert exc.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert exc.value.boundary is ModelBoundary.IDENTITY_RESOLVER


# --- B-1 Case B: the offered reference still works ---------------------------


def test_b1_the_offered_reference_resolves_normally():
    """C1 maps to the intended candidate; Slice 2 behaviour is unchanged."""
    service, store, _ = _run(_reply("C1"))
    service.record_interaction(SUBJECT, [_ev("second")])

    assert len(store.lineages.list_for_subject(SUBJECT)) == 1, "matched, not founded"
    (hypothesis,) = store.hypotheses.list_for_subject(SUBJECT)
    assert hypothesis.supporting_evidence_ids == ("evidence-1", "evidence-2")


# --- B-2 — governed rejection and complete audit provenance ------------------


def _expected_provenance() -> dict[str, str]:
    return {
        "resolver_id": RESOLVER_ID,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }


def test_b2_malformed_resolver_output_is_a_governed_rejection():
    """"not json" escaped as MalformedOutputError, so no governed record existed."""
    service, _, _ = _run("not json")

    with pytest.raises(GovernedRejection) as exc:
        service.record_interaction(SUBJECT, [_ev("second")])

    assert exc.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert exc.value.boundary is ModelBoundary.IDENTITY_RESOLVER
    assert exc.value.raw_response == "not json", "exact reply, not a summary"
    assert dict(exc.value.provenance) == _expected_provenance()


def test_b2_malformed_resolver_output_rolls_back_and_restores_counters():
    service, store, ids = _run("not json")
    with pytest.raises(GovernedRejection):
        service.record_interaction(SUBJECT, [_ev("second")])

    for name, store_obj in bundle_stores(store).items():
        lister = getattr(store_obj, "list_for_subject", None)
        if lister is None:
            continue
        rows = list(lister(SUBJECT))
        expected = 1 if name in {"evidence", "hypotheses", "lineages"} else 0
        assert len(rows) == expected, f"{name} changed under a rejected plan"

    assert ids.new_id("evidence") == "evidence-2"
    assert ids.new_id("req") == "req-2"


@pytest.mark.parametrize("payload", ["not json", _reply("hyp-1")])
def test_b2_the_rejected_plan_record_carries_the_full_resolver_provenance(payload):
    """The AUDIT RECORD, not merely the exception."""
    service, _, _ = _run(payload)
    with pytest.raises(GovernedRejection) as exc:
        service.record_interaction(SUBJECT, [_ev("second")])

    interaction = CASE_001.interactions[0]
    record = from_rejected_plan("sanuvia", interaction, ("ER-001",), exc.value)

    assert record.outcome is InteractionOutcome.REJECTED_PLAN
    assert record.governed_failure == "INVALID_APPRAISAL_RESPONSE"
    assert record.committed is False
    assert record.boundary == "IDENTITY_RESOLVER"
    assert record.boundary_raw_response == payload
    assert dict(record.boundary_provenance) == _expected_provenance()

    # Everything recoverable from the canonical JSON echo too.
    echoed = json.loads(record.raw)
    assert echoed["boundary"] == "IDENTITY_RESOLVER"
    assert echoed["boundary_raw_response"] == payload
    assert echoed["boundary_provenance"] == _expected_provenance()
    assert echoed["committed"] is False


def test_b2_the_appraisal_responses_are_kept_separate_from_the_resolver_reply():
    """Both boundaries were crossed; neither may overwrite the other."""
    service, _, _ = _run("not json")
    with pytest.raises(GovernedRejection) as exc:
        service.record_interaction(SUBJECT, [_ev("second")])

    record = from_rejected_plan(
        "sanuvia", CASE_001.interactions[0], ("ER-001",), exc.value
    )
    assert record.boundary_raw_response == "not json"
    # The appraiser produced no raw response on this path, but the field is
    # populated independently and is not the resolver's reply.
    assert record.appraisal_responses != ((("evidence-2"), "not json"),)
    assert all(raw != "not json" for _, raw in record.appraisal_responses)


# ===========================================================================
# B-3 — interaction-level extraction rejection
# ===========================================================================


def _observation(role: str) -> dict:
    return {
        "observation": "she left the room", "evidence_class": "behavioural",
        "reliability": 0.8, "classification_confidence": 0.9,
        "provenance_confidence": 0.9, "text_span": None,
        "role": role, "subject_kind": "participant", "subject": "pB",
    }


class _SecondTurnHasInvalidStanding:
    def __init__(self) -> None:
        self.calls = 0
        self.replies: list[str] = []

    def __call__(self, _request) -> str:
        self.calls += 1
        role = "event_observation" if self.calls == 1 else "resonance"
        reply = json.dumps({"evidence": [_observation(role)]})
        self.replies.append(reply)
        return reply


def _two_turn_case():
    client = _SecondTurnHasInvalidStanding()
    extractor = ExternalEvidenceExtractor(
        client=client, permitted_participants=("pA", "pB")
    )
    transcript = Transcript(
        "t-1", SubjectId("s-1"), shared_space_id("d"),
        (
            TranscriptInteraction(1, "seq-1", "she left the room", speaker="pA"),
            TranscriptInteraction(2, "seq-2", "that resonates", speaker="pA"),
        ),
    )
    extracted = pipeline.build_extracted_case(
        transcript, extractor, {}, {}, case_id="c-1", mode="real"
    )
    return extracted, client


def test_b3_an_invalid_later_interaction_does_not_abort_the_run():
    """The whole run previously aborted; now one interaction is rejected."""
    extracted, client = _two_turn_case()

    assert client.calls == 2, "the second turn was still extracted"
    assert len(extracted.case.interactions) == 2, "the run completed"


def test_b3_the_valid_interaction_is_unaffected():
    extracted, _ = _two_turn_case()
    first = extracted.case.interactions[0]

    assert first.pre_rejection is None
    assert len(first.evidence) == 1


def test_b3_the_invalid_interaction_is_rejected_and_admits_nothing():
    extracted, _ = _two_turn_case()
    second = extracted.case.interactions[1]

    assert second.pre_rejection is not None
    assert second.pre_rejection.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION
    assert second.evidence == (), "no evidence from a rejected interaction"


def test_b3_the_validated_extraction_output_is_preserved():
    """Q6: the COMPLETE extraction output survives on the rejection."""
    extracted, client = _two_turn_case()
    rejection = extracted.case.interactions[1].pre_rejection

    assert rejection.raw_response == client.replies[1]
    assert "resonance" in rejection.raw_response


def test_b3_the_condition_emits_a_rejected_plan_record_for_it():
    """Through the real condition, so the audit shape is the governed one."""
    extracted, client = _two_turn_case()
    condition = SanuviaPersistentCondition(extracted.case)
    condition.start()

    first = condition.step(extracted.case.interactions[0])
    second = condition.step(extracted.case.interactions[1])

    # The valid interaction is processed normally. It HOLDS rather than
    # commits only because this transcript carries no appraisal script, so
    # nothing was proposed -- the distinction that matters is that it is not a
    # rejection and its evidence was admitted.
    assert first.outcome is not InteractionOutcome.REJECTED_PLAN
    assert first.governed_failure is None
    assert first.ingested_evidence_ids

    assert second.outcome is InteractionOutcome.REJECTED_PLAN
    assert second.governed_failure == "EVIDENCE_ROLE_VIOLATION"
    assert second.committed is False
    assert second.boundary_raw_response == client.replies[1]


def test_b3_the_rejected_interaction_mutates_no_reasoning_state():
    extracted, _ = _two_turn_case()
    condition = SanuviaPersistentCondition(extracted.case)
    condition.start()
    condition.step(extracted.case.interactions[0])

    store = condition._store
    subject, space = extracted.case.subject_id, extracted.case.space_id
    before = (
        len(store.evidence.list_for_subject(subject, space_id=space)),
        len(store.hypotheses.list_for_subject(subject, space_id=space)),
        len(store.lineages.list_for_subject(subject, space_id=space)),
        len(store.dependencies.all_edges()),
    )

    condition.step(extracted.case.interactions[1])

    after = (
        len(store.evidence.list_for_subject(subject, space_id=space)),
        len(store.hypotheses.list_for_subject(subject, space_id=space)),
        len(store.lineages.list_for_subject(subject, space_id=space)),
        len(store.dependencies.all_edges()),
    )
    assert after == before, "the rejected interaction changed reasoning state"


def test_b3_the_run_matches_processing_only_the_valid_interaction():
    """Reasoning state is equivalent to a valid-only run."""
    extracted, _ = _two_turn_case()

    both = SanuviaPersistentCondition(extracted.case)
    both.start()
    for interaction in extracted.case.interactions:
        both.step(interaction)

    valid_only = SanuviaPersistentCondition(extracted.case)
    valid_only.start()
    valid_only.step(extracted.case.interactions[0])

    subject, space = extracted.case.subject_id, extracted.case.space_id

    def projection(condition):
        store = condition._store
        return (
            [e.id for e in store.evidence.list_for_subject(subject, space_id=space)],
            [
                (h.hypothesis_id, h.support.value)
                for h in store.hypotheses.list_for_subject(subject, space_id=space)
            ],
            [l.hypothesis_id
             for l in store.lineages.list_for_subject(subject, space_id=space)],
        )

    assert projection(both) == projection(valid_only)
