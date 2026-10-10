"""TD-19 — Scripted and External adapter parity.

The governed controls live behind the appraiser port, in ``src/sanuvia``, not
in either adapter. The parity assertion is what makes that structural rather
than asserted: an unresolvable hypothesis reference must produce the **same**
governed outcome whichever adapter produced it.

Fake clients only. No provider is selected, no key is read and nothing reaches
a network.
"""

from __future__ import annotations

from typing import Any

import json

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import Appraisal, EvidenceHandle
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


def _outcome_of(appraiser: Any) -> GovernedOutcome:
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


#: The exact reply the External fake returns, so tests can assert it verbatim
#: rather than merely asserting something non-empty came back.
_EXTERNAL_REPLY = json.dumps(
    {"supports": ["req-1::H99"], "contradicts": [], "proposals": []}
)


def _external_unknown() -> ExternalEvidenceAppraiser:
    """Fake client naming a handle that was never issued for this request."""
    return ExternalEvidenceAppraiser(client=lambda _prompt: _EXTERNAL_REPLY)


def test_td19_unknown_reference_produces_the_same_governed_outcome() -> None:
    """TD-19: identical governed outcome from both adapters."""
    scripted = _outcome_of(_scripted_unknown())
    external = _outcome_of(_external_unknown())
    assert scripted is external is GovernedOutcome.UNKNOWN_HYPOTHESIS_REFERENCE


def test_td19_neither_adapter_persists_anything_on_the_rejection() -> None:
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


def test_td19_neither_adapter_decides_the_rejection_itself() -> None:
    """TD-19: the adapter raises nothing; the governed control is behind the port.

    An adapter that validated references itself would pass the outcome test
    above while moving the decision into a layer with no authority to make it
    (§1.3, F-11). Both adapters must therefore RETURN an unresolvable
    reference rather than raise on it.
    """
    from sanuvia.application.ports.reasoning import (
    AppraisalRequest,
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


# --- TD-19 completion: classification, result shape, state equivalence ------


def _reject(appraiser: Any) -> tuple[GovernedRejection, Any]:
    """Run one interaction and return (rejection, store)."""
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store, appraiser=appraiser,
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    with pytest.raises(GovernedRejection) as exc:
        ReasoningService(deps).record_interaction(SUBJECT, [_ev("an observation")])
    return exc.value, store


def test_td19_offending_reference_classification_matches_across_paths() -> None:
    """TD-19 / N-4: the governed CLASSIFICATION of the offending reference.

    Not merely the same outcome: both adapters must classify the offending
    reference the same way. A handle that was never issued for this request is
    "never-issued", as distinct from one carrying another request's id, which
    is "cross-request" -- a different diagnosis of the same outcome.
    """
    from sanuvia.application.reasoning.handles import HandleTable

    scripted_exc, _ = _reject(_scripted_unknown())
    external_exc, _ = _reject(_external_unknown())

    scripted_refs = tuple(scripted_exc.references)
    external_refs = tuple(external_exc.references)
    assert scripted_refs and external_refs

    # Classified against the request that issued the handles. Both offending
    # references name a handle this request never issued, so both must
    # classify "never-issued" -- not merely "both rejected".
    table = HandleTable(
        request_id="req-1",
        observation=EvidenceHandle("req-1::E0"),
        observation_id=EvidenceRecordId("evidence-1"),
    )
    scripted_class = table.classify_unknown_evidence_handle(scripted_refs[0])
    external_class = table.classify_unknown_evidence_handle(external_refs[0])
    assert scripted_class == external_class == "never-issued"


def test_td19_result_shape_is_identical_across_paths() -> None:
    """TD-19: committed:false and the governed discriminators agree."""
    scripted_exc, _ = _reject(_scripted_unknown())
    external_exc, _ = _reject(_external_unknown())

    assert scripted_exc.outcome is external_exc.outcome
    assert scripted_exc.breach_kind is external_exc.breach_kind
    assert scripted_exc.boundary is external_exc.boundary
    # committed:false -- neither path produced an InteractionResult at all,
    # which is the strongest form of "not committed".


def test_td19_raw_response_is_excluded_from_parity_and_preserved_per_path() -> None:
    """TD-19 excludes raw_response from the cross-path equality, by design.

    ScriptedAppraiser produces no raw response by construction, so comparing
    the two for EQUALITY asserted the absence as a shared property -- which is
    how a missing External raw response could look like parity. The design's
    own note says raw_response is excluded from TD-19 for exactly this reason,
    so each path is asserted against what it is supposed to produce.
    """
    scripted_exc, _ = _reject(_scripted_unknown())
    external_exc, _ = _reject(_external_unknown())

    # Scripted: None by construction.
    assert scripted_exc.raw_response is None

    # External: the fake client's exact reply, not merely non-empty.
    assert external_exc.raw_response == _EXTERNAL_REPLY

    # And the interaction-level audit carries it, attributed to its
    # observation (§5.8, F-15).
    assert external_exc.appraisal_responses == (("evidence-1", _EXTERNAL_REPLY),)
    assert scripted_exc.appraisal_responses == (("evidence-1", None),)


def test_td19_reasoning_state_is_completely_equivalent_across_paths() -> None:
    """TD-19: every store in the bundle, not only evidence and lineages.

    Checking two stores would let a divergence hide in any of the other
    thirteen, so the comparison enumerates the bundle.
    """
    from sanuvia.application.reasoning.unit_of_work import bundle_stores

    _, scripted_store = _reject(_scripted_unknown())
    _, external_store = _reject(_external_unknown())

    scripted_bundle = bundle_stores(scripted_store)
    external_bundle = bundle_stores(external_store)
    assert set(scripted_bundle) == set(external_bundle)

    for name in sorted(scripted_bundle):
        lister = getattr(scripted_bundle[name], "list_for_subject", None)
        if lister is None:
            continue
        scripted_rows = list(lister(SUBJECT))
        external_rows = list(external_bundle[name].list_for_subject(SUBJECT))
        assert scripted_rows == external_rows == [], (
            f"{name}: state diverged or survived the rejection"
        )


def test_td19_neither_adapter_persists_evidence_or_lineage_state() -> None:
    """TD-19, stated explicitly for the two stores the defect would touch."""
    for appraiser in (_scripted_unknown(), _external_unknown()):
        _, store = _reject(appraiser)
        assert store.evidence.list_for_subject(SUBJECT) == []
        assert store.lineages.list_for_subject(SUBJECT) == []
        assert list(store.statement_versions.history("hyp-1")) == []
        assert store.ledger.read(SUBJECT) == []


def test_td19_identifier_counters_agree_across_paths() -> None:
    """TD-19: a rejection must leave both paths equally reusable."""
    for appraiser in (_scripted_unknown(), _external_unknown()):
        store = InMemoryReasoningStore()
        ids = SequentialIdGenerator()
        deps = build_in_memory_dependencies(
            store=store, appraiser=appraiser, ids=ids, clock=ManualClock(),
        )
        with pytest.raises(GovernedRejection):
            ReasoningService(deps).record_interaction(SUBJECT, [_ev("an observation")])
        assert ids.new_id("evidence") == "evidence-1"
        assert ids.new_id("req") == "req-1"
