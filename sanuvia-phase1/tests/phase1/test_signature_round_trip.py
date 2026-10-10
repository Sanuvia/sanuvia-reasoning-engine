"""The commitment signature crosses the model boundary in BOTH directions.

§2 C gives ``CandidateProposal`` a signature, and §2 H defines what it commits
to. Until this was wired, the signature was computed on the engine side and
then dropped at the adapter: the prompt showed the model only a handle and a
statement, and the response schema had nowhere to put one back.

Fake clients only. No provider is selected and nothing reaches a network.
"""

from __future__ import annotations

from typing import Any

import json

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import EvidenceInput, ReasoningService
from sanuvia.domain import (
    VOICE_SANUVIA_WORKING_READING,
    ClaimClass,
    EvidenceClass,
    Stance,
)

from sanuvia_phase1.evidence_appraisers.external import (
    AppraisalPrompt,
    ExternalEvidenceAppraiser,
)
from sanuvia_phase1.failures import MalformedOutputError

SUBJECT = "subject-sig"


def _ev(text: str) -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE, content=text,
        source="extractor:test", reliability=0.8, classification_confidence=0.9,
    )


def _service(client: Any) -> tuple[ReasoningService, InMemoryReasoningStore]:
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store, appraiser=ExternalEvidenceAppraiser(client=client),
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    return ReasoningService(deps), store


def _reply(prompt: AppraisalPrompt, *, claim: str = "behaviour_pattern",
           stance: str = "affirms",
           scope: str = "recurring") -> str:
    return json.dumps({
        "supports": [], "contradicts": [],
        "proposals": [{
            "local_ref": "p1",
            "statement": "withdraws when challenged",
            "signature": {
                "subject": prompt.participants[0],
                "claim_class": claim, "stance": stance, "temporal_scope": scope,
            },
        }],
    })


def test_returned_signature_reaches_the_committed_statement_version() -> None:
    """Inbound: the model's stated signature becomes the stored version."""
    svc, store = _service(_reply)
    svc.record_interaction(SUBJECT, [_ev("an observation")])

    (lineage,) = store.lineages.list_for_subject(SUBJECT)
    (version,) = list(store.statement_versions.history(lineage.hypothesis_id))

    assert version.claim_class is ClaimClass.BEHAVIOUR_PATTERN
    assert version.stance is Stance.AFFIRMS
    assert version.temporal_scope == "recurring"

    # attribution is NOT the model's: it is the governed voice label.
    assert lineage.attribution == VOICE_SANUVIA_WORKING_READING


def test_prompt_carries_the_signature_of_each_active_hypothesis() -> None:
    """Outbound: the model sees what each existing commitment commits to."""
    seen: list[AppraisalPrompt] = []

    def client(prompt: AppraisalPrompt) -> str:
        seen.append(prompt)
        if prompt.active_hypotheses:
            return json.dumps({"supports": [], "contradicts": [], "proposals": []})
        return _reply(prompt)

    svc, _ = _service(client)
    svc.record_interaction(SUBJECT, [_ev("first")])
    svc.record_interaction(SUBJECT, [_ev("second")])

    (offered,) = seen[1].active_hypotheses
    assert offered.statement == "withdraws when challenged"
    assert offered.claim_class == "behaviour_pattern"
    assert offered.stance == "affirms"
    assert offered.temporal_scope == "recurring"
    assert offered.attribution == VOICE_SANUVIA_WORKING_READING
    # Request-scoped only: no durable identifier crosses the boundary (TD-V1).
    assert offered.subject in seen[1].participants


def test_prompt_lists_the_participant_labels_a_subject_may_name() -> None:
    """Outbound: without these the model cannot state a resolvable subject."""
    seen: list[AppraisalPrompt] = []

    def client(prompt: AppraisalPrompt) -> str:
        seen.append(prompt)
        return _reply(prompt)

    svc, _ = _service(client)
    svc.record_interaction(SUBJECT, [_ev("an observation")])
    assert seen[0].participants, "participant labels must be supplied"


@pytest.mark.parametrize("field,value", [
    ("claim_class", "not_a_claim_class"),
    ("stance", "maybe"),
])
def test_signature_values_outside_the_governed_enums_are_rejected(
    field: str, value: str
) -> None:
    """Rejected, never coerced or defaulted."""
    def client(prompt: AppraisalPrompt) -> str:
        payload = json.loads(_reply(prompt))
        payload["proposals"][0]["signature"][field] = value
        return json.dumps(payload)

    svc, store = _service(client)
    with pytest.raises(MalformedOutputError) as exc:
        svc.record_interaction(SUBJECT, [_ev("an observation")])
    assert field in str(exc.value)
    assert store.lineages.list_for_subject(SUBJECT) == []


def test_a_missing_signature_is_rejected_not_defaulted() -> None:
    def client(prompt: AppraisalPrompt) -> str:
        return json.dumps({
            "supports": [], "contradicts": [],
            "proposals": [{"local_ref": "p1", "statement": "s"}],
        })

    svc, _ = _service(client)
    with pytest.raises(MalformedOutputError, match="signature"):
        svc.record_interaction(SUBJECT, [_ev("an observation")])


def test_model_supplied_attribution_is_rejected() -> None:
    """§2 H: the voice is not the model's to choose.

    Accepting it would let the model decide whether its own interpretation is
    the participant's own commitment -- the distinction the immutable half of
    the lineage key exists to keep.
    """
    def client(prompt: AppraisalPrompt) -> str:
        payload = json.loads(_reply(prompt))
        payload["proposals"][0]["signature"]["attribution"] = "participant account"
        return json.dumps(payload)

    svc, _ = _service(client)
    with pytest.raises(MalformedOutputError, match="attribution"):
        svc.record_interaction(SUBJECT, [_ev("an observation")])


def test_an_invented_participant_label_is_refused_by_the_engine() -> None:
    """The adapter does not validate the subject; the engine does (§1.3, F-11)."""
    from sanuvia.domain import GovernedRejection

    def client(prompt: AppraisalPrompt) -> str:
        payload = json.loads(_reply(prompt))
        payload["proposals"][0]["signature"]["subject"] = "P_invented"
        return json.dumps(payload)

    svc, store = _service(client)
    with pytest.raises(GovernedRejection):
        svc.record_interaction(SUBJECT, [_ev("an observation")])
    assert store.lineages.list_for_subject(SUBJECT) == []
