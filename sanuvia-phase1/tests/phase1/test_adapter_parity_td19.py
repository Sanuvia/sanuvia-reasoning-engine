"""TD-19 — Scripted and External adapter parity.

The governed controls live behind the appraiser port, in ``src/sanuvia``, not
in either adapter. The parity assertion is what makes that structural rather
than asserted: an unresolvable hypothesis reference must produce the **same**
governed outcome whichever adapter produced it.

Fake clients only. No provider is selected, no key is read and nothing reaches
a network.
"""

from __future__ import annotations

import json

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import Appraisal
from sanuvia.domain import (
    EvidenceClass,
    EvidenceRecordId,
    GovernedOutcome,
    GovernedRejection,
)

from sanuvia_phase1.evidence_appraisers.external import ExternalEvidenceAppraiser

SUBJECT = "subject-parity"


def _ev(text: str) -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE, content=text,
        source="extractor:test", reliability=0.8, classification_confidence=0.9,
    )


def _outcome_of(appraiser) -> GovernedOutcome:
    deps = build_in_memory_dependencies(
        store=InMemoryReasoningStore(), appraiser=appraiser,
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    with pytest.raises(GovernedRejection) as exc:
        ReasoningService(deps).record_interaction(SUBJECT, [_ev("an observation")])
    return exc.value.outcome


def _scripted_unknown() -> ScriptedAppraiser:
    """Authored reference that resolves to nothing -> unresolvable handle."""
    return ScriptedAppraiser(
        {EvidenceRecordId("evidence-1"): Appraisal(supports=("H_never_proposed",))}
    )


def _external_unknown() -> ExternalEvidenceAppraiser:
    """Fake client naming a handle that was never issued for this request."""
    def client(_prompt) -> str:
        return json.dumps(
            {"supports": ["req-1::H99"], "contradicts": [], "proposals": []}
        )

    return ExternalEvidenceAppraiser(client=client)


def test_td19_unknown_reference_produces_the_same_governed_outcome():
    """TD-19: identical governed outcome from both adapters."""
    scripted = _outcome_of(_scripted_unknown())
    external = _outcome_of(_external_unknown())
    assert scripted is external is GovernedOutcome.UNKNOWN_HYPOTHESIS_REFERENCE


def test_td19_neither_adapter_persists_anything_on_the_rejection():
    """TD-19: parity covers the mutation consequence, not just the outcome."""
    for appraiser in (_scripted_unknown(), _external_unknown()):
        store = InMemoryReasoningStore()
        deps = build_in_memory_dependencies(
            store=store, appraiser=appraiser,
            ids=SequentialIdGenerator(), clock=ManualClock(),
        )
        with pytest.raises(GovernedRejection):
            ReasoningService(deps).record_interaction(SUBJECT, [_ev("an observation")])
        assert store.evidence.list_for_subject(SUBJECT) == []
        assert store.lineages.list_for_subject(SUBJECT) == []


def test_td19_neither_adapter_decides_the_rejection_itself():
    """TD-19: the adapter raises nothing; the governed control is behind the port.

    An adapter that validated references itself would pass the outcome test
    above while moving the decision into a layer with no authority to make it
    (§1.3, F-11). Both adapters must therefore RETURN an unresolvable
    reference rather than raise on it.
    """
    from sanuvia.application.ports.reasoning import (
        AppraisalRequest, ObservationView, EvidenceHandle,
    )

    request = AppraisalRequest(
        request_id="req-1",
        subject_id=SUBJECT,
        space_id="space:default",
        observation=ObservationView(handle=EvidenceHandle("req-1::E0"),
                                    content="an observation", standing=None),
        existing=(),
        divergence_candidates=(),
        participants=(),
        observation_id=EvidenceRecordId("evidence-1"),
    )

    scripted_response = _scripted_unknown().appraise(request)
    external_response = _external_unknown().appraise(request)

    # Both returned a response carrying an unresolvable reference...
    assert len(scripted_response.bearings) == 1
    assert len(external_response.bearings) == 1
    # ... and neither dropped it, which would have silently emptied a
    # governed failure.
    assert scripted_response.bearings[0].target
    assert external_response.bearings[0].target
