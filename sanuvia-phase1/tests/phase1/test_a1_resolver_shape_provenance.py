"""Resolver shape failures carry complete audit provenance (A-1, R-1, O-1).

Two valid-JSON-but-unusable resolver shapes were rejected at the application
layer, where only ``resolver_id`` is available. The rejected-plan record could
therefore not say which prompt or schema version produced the unusable reply.

They are now rejected at ``validate_identity_resolution``, the adapter's
validation boundary, which is where the resolver's provenance lives. The
equivalent application-layer checks remain as defence in depth.

These drive the real caller path with a fake client, exactly as the B-2 tests
do. The adapter validation boundary is exercised; no rejection is hand-built.
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
from sanuvia.application.reasoning.identity import DeterministicAdjudicator
from sanuvia.application.reasoning.unit_of_work import bundle_stores
from sanuvia.domain import (
    VOICE_SANUVIA_WORKING_READING,
    ClaimClass,
    CommitmentSignature,
    EvidenceClass,
    GovernedOutcome,
    GovernedRejection,
    IdentityDecision,
    IdentityOutcome,
    ModelBoundary,
    Stance,
)

from sanuvia_phase1.capture import from_rejected_plan
from sanuvia_phase1.identity_resolvers import RESOLVER_ID, ExternalIdentityResolver
from sanuvia_phase1.identity_resolvers.external import PROMPT_VERSION, SCHEMA_VERSION
from sanuvia_phase1.trajectory import InteractionOutcome

SUBJECT = "subject-a1"

#: Valid JSON, governed outcome, unusable shape. One rule per outcome, so the
#: four together are exhaustive over the identity vocabulary.
MATCH_WITHOUT_REF = json.dumps({
    "outcome": "match_existing", "matched_ref": None,
    "rationale": "same commitment", "confidence": 0.7,
})
DISTINCT_WITH_REF = json.dumps({
    "outcome": "distinct_new", "matched_ref": "C1",
    "rationale": "a different commitment", "confidence": 0.7,
})
#: R-1 -- a refinement must say what it refines.
REFINE_WITHOUT_REF = json.dumps({
    "outcome": "refine_existing", "matched_ref": None,
    "rationale": "narrower", "confidence": 0.7,
})
#: O-1 -- an unresolved candidate names nothing by definition. This was
#: ACCEPTED before the repair, not merely under-provenanced.
AMBIGUOUS_WITH_REF = json.dumps({
    "outcome": "ambiguous_review_required", "matched_ref": "C1",
    "rationale": "cannot distinguish", "confidence": 0.7,
})

SHAPES = pytest.mark.parametrize(
    "payload",
    [MATCH_WITHOUT_REF, DISTINCT_WITH_REF, REFINE_WITHOUT_REF, AMBIGUOUS_WITH_REF],
    ids=[
        "match_existing_without_ref",
        "distinct_new_with_ref",
        "refine_existing_without_ref",
        "ambiguous_review_required_with_ref",
    ],
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


def _ev(text: str) -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE, content=text,
        source="extractor:test", reliability=0.8, classification_confidence=0.9,
    )


def _service(resolver_reply: str):
    store = InMemoryReasoningStore()
    ids = SequentialIdGenerator()
    deps = build_in_memory_dependencies(
        store=store, appraiser=_ProposesTwoReadings(), ids=ids, clock=ManualClock(),
        identity_resolver=ExternalIdentityResolver(client=lambda _p: resolver_reply),
    )
    service = ReasoningService(deps)
    service.record_interaction(SUBJECT, [_ev("first")])  # founds the lineage
    return service, store, ids


def _reject(payload: str):
    service, store, ids = _service(payload)
    with pytest.raises(GovernedRejection) as exc:
        service.record_interaction(SUBJECT, [_ev("second")])
    return exc.value, store, ids


# --- the governed rejection ---------------------------------------------------


@SHAPES
def test_the_shape_is_a_governed_identity_resolver_rejection(payload):
    rejection, _, _ = _reject(payload)

    assert rejection.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert rejection.boundary is ModelBoundary.IDENTITY_RESOLVER


@SHAPES
def test_the_exact_raw_resolver_response_is_preserved(payload):
    rejection, _, _ = _reject(payload)
    assert rejection.raw_response == payload, "the exact reply, not a summary"


@SHAPES
def test_the_rejection_carries_complete_resolver_provenance(payload):
    """The point of the repair: all three, not just resolver_id."""
    rejection, _, _ = _reject(payload)
    provenance = dict(rejection.provenance)

    assert provenance["resolver_id"] == RESOLVER_ID
    assert provenance["prompt_version"] == PROMPT_VERSION
    assert provenance["schema_version"] == SCHEMA_VERSION


# --- the rejected-plan audit record ------------------------------------------


@SHAPES
def test_the_rejected_plan_record_carries_the_full_audit_payload(payload):
    rejection, _, _ = _reject(payload)
    record = from_rejected_plan(
        "sanuvia", CASE_001.interactions[0], ("ER-001",), rejection
    )

    assert record.outcome is InteractionOutcome.REJECTED_PLAN
    assert record.governed_failure == "INVALID_APPRAISAL_RESPONSE"
    assert record.boundary == "IDENTITY_RESOLVER"
    assert record.committed is False
    assert record.boundary_raw_response == payload
    assert dict(record.boundary_provenance) == {
        "resolver_id": RESOLVER_ID,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }

    # Recoverable from the canonical JSON echo as well.
    echoed = json.loads(record.raw)
    assert echoed["boundary"] == "IDENTITY_RESOLVER"
    assert echoed["boundary_raw_response"] == payload
    assert echoed["boundary_provenance"]["prompt_version"] == PROMPT_VERSION
    assert echoed["boundary_provenance"]["schema_version"] == SCHEMA_VERSION
    assert echoed["committed"] is False


# --- rollback -----------------------------------------------------------------


@SHAPES
def test_reasoning_state_is_unchanged(payload):
    _, store, _ = _reject(payload)

    for name, store_obj in bundle_stores(store).items():
        lister = getattr(store_obj, "list_for_subject", None)
        if lister is None:
            continue
        rows = list(lister(SUBJECT))
        expected = 1 if name in {"evidence", "hypotheses", "lineages"} else 0
        assert len(rows) == expected, f"{name} changed under a rejected plan"

    # The surviving lineage is still supported only by its original evidence.
    (hypothesis,) = store.hypotheses.list_for_subject(SUBJECT)
    assert hypothesis.supporting_evidence_ids == ("evidence-1",)
    assert len(list(store.statement_versions.history("hyp-1"))) == 1


@SHAPES
def test_no_identifier_is_consumed(payload):
    _, _, ids = _reject(payload)
    assert ids.new_id("evidence") == "evidence-2"
    assert ids.new_id("req") == "req-2"


# --- defence in depth ---------------------------------------------------------


def _decision(outcome: IdentityOutcome, matched):
    return IdentityDecision(
        outcome=outcome, candidate_local_ref="c1", matched_hypothesis_id=matched,
    )


class _ReturnsDecision:
    """A resolver that bypasses the adapter's validation entirely."""

    resolver_id = "test-double"

    def __init__(self, decision: IdentityDecision) -> None:
        self._decision = decision

    def resolve(self, candidate, plausible):
        return self._decision


@pytest.mark.parametrize("outcome,matched", [
    (IdentityOutcome.MATCH_EXISTING, None),
    (IdentityOutcome.DISTINCT_NEW, "hyp-1"),
    (IdentityOutcome.REFINE_EXISTING, None),
], ids=[
    "match_existing_without_ref",
    "distinct_new_with_ref",
    "refine_existing_without_ref",
])
def test_the_application_still_rejects_these_shapes_from_another_path(
    outcome, matched
):
    """Defence in depth: the application guard remains and is not weakened.

    The adapter now catches these shapes first, so this reaches the application
    check by supplying an IdentityDecision directly -- the case the guard
    exists for, since an invalid decision could arrive from a path that does
    not go through ``validate_identity_resolution``.

    ``AMBIGUOUS_REVIEW_REQUIRED`` with a reference (O-1) is deliberately absent
    from this set: the application has no equivalent guard, because a stray
    ``matched_hypothesis_id`` on a parked decision is inert -- the parked
    adjudication is built from ``plausible_matches``, not from it. Adding one
    would be new governed behaviour beyond the authorised shape rules, so it is
    reported rather than invented. The adapter rule is what enforces O-1.
    """
    from sanuvia.application.reasoning.identity import LineageView

    key = ("p1", VOICE_SANUVIA_WORKING_READING)
    lineage = LineageView(hypothesis_id="hyp-1", key=key, current_stance=Stance.OPEN)
    signature = CommitmentSignature(
        subject="p1", attribution=VOICE_SANUVIA_WORKING_READING,
        claim_class=ClaimClass.INTERPRETATION, stance=Stance.OPEN,
    )
    proposal = CandidateProposal(
        "c1", "a second reading",
        CommitmentSignatureView(
            subject="p1", attribution=VOICE_SANUVIA_WORKING_READING,
            claim_class=ClaimClass.INTERPRETATION, stance=Stance.OPEN,
        ),
    )

    adjudicator = DeterministicAdjudicator(
        resolver=_ReturnsDecision(_decision(outcome, matched))
    )
    with pytest.raises(GovernedRejection) as exc:
        adjudicator.adjudicate(
            proposal, signature, committed={key: [lineage]}, in_flight={},
        )

    assert exc.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert exc.value.boundary is ModelBoundary.IDENTITY_RESOLVER


# --- R-1: the offered-reference requirement ----------------------------------


@pytest.mark.parametrize("unoffered", ["hyp-1", "C99"], ids=["durable_id", "unknown"])
def test_refine_existing_must_name_an_offered_reference(unoffered: str) -> None:
    """R-1: a named ref must be one THIS request offered.

    Enforced by the closed reference vocabulary in the adapter (B-1), which
    every non-null ref passes through, so naming a durable id cannot bypass it
    on the refine path any more than on the match path. ``hyp-1`` is a real
    lineage here, so this is not a near miss.
    """
    payload = json.dumps({
        "outcome": "refine_existing", "matched_ref": unoffered,
        "rationale": "narrower", "confidence": 0.7,
    })
    rejection, store, _ = _reject(payload)

    assert rejection.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert rejection.boundary is ModelBoundary.IDENTITY_RESOLVER
    assert "was not offered" in str(rejection)
    assert dict(rejection.provenance) == {
        "resolver_id": RESOLVER_ID,
        "prompt_version": PROMPT_VERSION,
        "schema_version": SCHEMA_VERSION,
    }
    assert [l.hypothesis_id for l in store.lineages.list_for_subject(SUBJECT)] == [
        "hyp-1"
    ], "the durable lineage really is called hyp-1"


# --- valid shapes are untouched ----------------------------------------------


def test_refine_existing_with_an_offered_reference_still_resolves() -> None:
    """R-1 must not disturb the valid refinement path."""
    service, store, _ = _service(json.dumps({
        "outcome": "refine_existing", "matched_ref": "C1",
        "rationale": "narrower", "confidence": 0.7,
    }))
    service.record_interaction(SUBJECT, [_ev("second")])

    (lineage,) = store.lineages.list_for_subject(SUBJECT)
    versions = list(store.statement_versions.history(lineage.hypothesis_id))
    assert [v.statement for v in versions] == ["the first reading", "a second reading"]


def test_ambiguous_review_required_with_a_null_reference_still_parks() -> None:
    """O-1 must not change valid ambiguous-review parking."""
    service, store, _ = _service(json.dumps({
        "outcome": "ambiguous_review_required", "matched_ref": None,
        "rationale": "cannot distinguish", "confidence": 0.7,
    }))
    service.record_interaction(SUBJECT, [_ev("second")])

    assert len(store.lineages.list_for_subject(SUBJECT)) == 1, "nothing founded"
    (parked,) = store.identity_adjudications.list_for_subject(SUBJECT)
    assert parked.decision.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    assert parked.candidate_statement == "a second reading"
    assert parked.plausible_matches, "plausible candidates are preserved"


# --- raw-response fidelity ----------------------------------------------------


@SHAPES
def test_the_raw_response_is_preserved_byte_for_byte(payload: str) -> None:
    """Including whitespace: the audit holds what the model actually sent."""
    spaced = "  " + payload + "\n"
    rejection, _, _ = _reject(spaced)
    assert rejection.raw_response == spaced
