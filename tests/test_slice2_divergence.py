"""Divergence candidate construction and space_kind (§2 J.1, §2 J.2).

These land together by design. Candidate construction without ``space_kind``
would leave check 8b's "divergence requires a shared space" test a no-op, which
is the half-wired disclosure path the coupling exists to prevent -- so both
halves are exercised here.

Divergence is evidence <-> evidence, symmetric, co-valid, and separate from
contradiction and from the support axis.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import (
    AppraisalResponse,
    DivergenceProposal,
)
from sanuvia.domain import (
    DEFAULT_SPACE_ID,
    DependencyRelation,
    EvidenceClass,
    EvidenceRole,
    EvidenceSourceKind,
    EvidenceStanding,
    EvidenceSubjectKind,
    GovernedOutcome,
    GovernedRejection,
    SpaceKind,
    personal_space_id,
    shared_space_id,
    space_kind_of,
)

SUBJECT = "subject-div"
SHARED = shared_space_id("dyad-1")
PERSONAL = personal_space_id("pA")


def _account(text: str, source: str, subject: str = "pX") -> EvidenceInput:
    """A participant account -- the only role divergence candidates may hold."""
    return EvidenceInput(
        subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE, content=text,
        source="extractor:test", reliability=0.8, classification_confidence=0.9,
        standing=EvidenceStanding(
            source_kind=EvidenceSourceKind.PARTICIPANT,
            subject_kind=EvidenceSubjectKind.PARTICIPANT,
            role=EvidenceRole.ACCOUNT, source_id=source, subject_id=subject,
        ),
    )


class _CapturesThenDiverges:
    """Records each request; proposes divergence against the first candidate."""

    def __init__(self, *, propose: bool = True, twice: bool = False) -> None:
        self.requests: list = []
        self._propose, self._twice = propose, twice

    def appraise(self, request):
        self.requests.append(request)
        if not self._propose or not request.divergence_candidates:
            return AppraisalResponse()
        target = request.divergence_candidates[0].handle
        proposals = (DivergenceProposal(with_evidence=target),)
        if self._twice:
            proposals = proposals * 2
        return AppraisalResponse(divergences=proposals)


def _service(appraiser, *, store=None):
    store = store or InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store, appraiser=appraiser,
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    return ReasoningService(deps), store


# --- 1/2. eligible candidates are constructed, evidence <-> evidence ---------


def test_eligible_divergence_candidates_are_constructed():
    appraiser = _CapturesThenDiverges(propose=False)
    service, _ = _service(appraiser)
    service.record_interaction(SUBJECT, [_account("she left first", "pA")],
                               space_id=SHARED)
    service.record_interaction(SUBJECT, [_account("he left first", "pB")],
                               space_id=SHARED)

    assert appraiser.requests[0].divergence_candidates == ()
    assert len(appraiser.requests[1].divergence_candidates) == 1, (
        "the other participant's account of the same subject is a candidate"
    )


def test_candidates_are_evidence_not_hypotheses():
    appraiser = _CapturesThenDiverges(propose=False)
    service, _ = _service(appraiser)
    service.record_interaction(SUBJECT, [_account("she left first", "pA")],
                               space_id=SHARED)
    service.record_interaction(SUBJECT, [_account("he left first", "pB")],
                               space_id=SHARED)

    candidate = appraiser.requests[1].divergence_candidates[0]
    assert hasattr(candidate, "content"), "an evidence view, not a hypothesis view"
    assert not hasattr(candidate, "statement")


@pytest.mark.parametrize("same_source,same_subject,expected", [
    ("pA", "pX", 0),   # rule 5: same source -> not a candidate
    ("pB", "pY", 0),   # rule 4: different subject -> not a candidate
    ("pB", "pX", 1),   # eligible
])
def test_candidate_eligibility_follows_the_approved_rules(
    same_source, same_subject, expected
):
    appraiser = _CapturesThenDiverges(propose=False)
    service, _ = _service(appraiser)
    service.record_interaction(SUBJECT, [_account("first", "pA", "pX")],
                               space_id=SHARED)
    service.record_interaction(
        SUBJECT, [_account("second", same_source, same_subject)], space_id=SHARED
    )
    assert len(appraiser.requests[1].divergence_candidates) == expected


# --- 3/4. one canonical symmetric relationship -------------------------------


def _run_divergence(appraiser=None, space=SHARED):
    appraiser = appraiser or _CapturesThenDiverges()
    service, store = _service(appraiser)
    service.record_interaction(SUBJECT, [_account("she left first", "pA")],
                               space_id=space)
    service.record_interaction(SUBJECT, [_account("he left first", "pB")],
                               space_id=space)
    edges = [e for e in store.dependencies.all_edges()
             if e.relation is DependencyRelation.DIVERGES_WITH]
    return store, edges


def test_a_canonical_symmetric_relationship_is_produced():
    _, edges = _run_divergence()
    assert len(edges) == 1
    (edge,) = edges
    # Canonical ordering: the relationship is one edge whichever direction it
    # was proposed from. Direction is an ordering artifact, not causal.
    assert edge.from_ref < edge.to_ref


def test_proposing_the_same_partner_twice_in_one_response_is_rejected():
    """Check 2: a repeated divergence partner is a governed failure.

    Stronger than silent de-duplication -- the response is incoherent, and
    quietly collapsing it would hide that.
    """
    with pytest.raises(GovernedRejection) as exc:
        _run_divergence(_CapturesThenDiverges(twice=True))
    assert exc.value.outcome is GovernedOutcome.INVALID_DIVERGENCE_PLAN
    assert "duplicate divergence partner" in str(exc.value)


def test_a_recorded_pair_is_excluded_from_later_candidate_sets():
    """Rule 6b, at the rule: an already-paired record is not offered again."""
    from sanuvia.application.reasoning.handles import build_divergence_candidates

    service, store = _service(_CapturesThenDiverges(propose=False))
    service.record_interaction(SUBJECT, [_account("first", "pA")], space_id=SHARED)
    service.record_interaction(SUBJECT, [_account("second", "pB")], space_id=SHARED)
    records = list(store.evidence.list_for_subject(SUBJECT, space_id=SHARED))
    first, second = records[0], records[1]

    # Unpaired: the other account is a candidate.
    assert build_divergence_candidates(
        observation=second, admitted=records, existing_pairs=frozenset()
    ) == (first,)

    # Once the pair is recorded, it is excluded BEFORE disclosure.
    paired = frozenset({(first.id, second.id)})
    assert build_divergence_candidates(
        observation=second, admitted=records, existing_pairs=paired
    ) == ()


def test_a_distinct_later_account_forms_its_own_relationship():
    """A new account is a NEW pair, not a duplicate of the recorded one."""
    appraiser = _CapturesThenDiverges()
    service, store = _service(appraiser)
    service.record_interaction(SUBJECT, [_account("she left first", "pA")],
                               space_id=SHARED)
    service.record_interaction(SUBJECT, [_account("he left first", "pB")],
                               space_id=SHARED)
    service.record_interaction(SUBJECT, [_account("a third account", "pB")],
                               space_id=SHARED)

    edges = [e for e in store.dependencies.all_edges()
             if e.relation is DependencyRelation.DIVERGES_WITH]
    pairs = {(e.from_ref, e.to_ref) for e in edges}
    assert len(pairs) == len(edges), "each relationship is recorded once"
    assert len(pairs) == 2, "two distinct pairs, not one pair twice"
    # The first request had nothing to diverge from.
    assert appraiser.requests[0].divergence_candidates == ()


# --- 5. divergence is not contradiction --------------------------------------


def test_divergence_changes_no_hypothesis_or_support():
    """Separate from contradiction and from the support axis."""
    store, edges = _run_divergence()
    assert len(edges) == 1
    assert store.hypotheses.list_for_subject(SUBJECT, space_id=SHARED) == []
    # Both accounts remain admitted and co-valid: nothing was withdrawn.
    assert len(store.evidence.list_for_subject(SUBJECT, space_id=SHARED)) == 2


def test_divergence_relation_is_distinct_from_contradiction():
    _, edges = _run_divergence()
    assert edges[0].relation is DependencyRelation.DIVERGES_WITH
    assert edges[0].relation is not DependencyRelation.CONTRADICTS


# --- 6-9. space_kind, disclosure ---------------------------------------------


def test_space_kind_is_derived_and_supplied():
    assert space_kind_of(SHARED) is SpaceKind.SHARED
    assert space_kind_of(PERSONAL) is SpaceKind.PERSONAL
    assert space_kind_of(DEFAULT_SPACE_ID) is None


@pytest.mark.parametrize("space", [PERSONAL, DEFAULT_SPACE_ID])
def test_a_non_shared_space_offers_no_divergence_candidates(space):
    """Rule 7 at construction: nothing can be disclosed across the boundary."""
    appraiser = _CapturesThenDiverges(propose=False)
    service, _ = _service(appraiser)
    service.record_interaction(SUBJECT, [_account("first", "pA")], space_id=space)
    service.record_interaction(SUBJECT, [_account("second", "pB")], space_id=space)

    assert all(r.divergence_candidates == () for r in appraiser.requests)


def test_unauthorised_disclosure_is_rejected_before_mutation():
    """Check 8b: a DIVERGES_WITH edge in a non-shared space fails validation.

    Constructed by hand, because construction already refuses to offer the
    candidate -- which is the point: the check re-verifies before mutation what
    rule 7 enforced at construction, so a plan built another way still fails.
    """
    from sanuvia.application.reasoning.plan_validation import RevisionPlan, validate_plan
    from sanuvia.domain import DependencyEdge, DependencyEdgeId, ObjectRef

    service, store = _service(_CapturesThenDiverges(propose=False))
    service.record_interaction(SUBJECT, [_account("first", "pA")], space_id=PERSONAL)
    service.record_interaction(SUBJECT, [_account("second", "pB")], space_id=PERSONAL)
    records = list(store.evidence.list_for_subject(SUBJECT, space_id=PERSONAL))

    a, b = ObjectRef(str(records[0].id)), ObjectRef(str(records[1].id))
    plan = RevisionPlan(
        subject_id=SUBJECT, space_id=PERSONAL, admitted=tuple(records), appraised=(),
        edges=(DependencyEdge(id=DependencyEdgeId("dep-1"), from_ref=a, to_ref=b,
                              relation=DependencyRelation.DIVERGES_WITH,
                              created_at=datetime.now(timezone.utc)),),
        intended_evidence_ids=(),
    )
    with pytest.raises(GovernedRejection) as exc:
        validate_plan(
            plan,
            committed_evidence={r.id: r for r in records},
            active_hypotheses={},
            space_kind=space_kind_of(PERSONAL),
        )
    assert exc.value.outcome is GovernedOutcome.INVALID_DIVERGENCE_PLAN
    assert "shared reasoning space" in str(exc.value)


def test_authorised_shared_space_disclosure_succeeds():
    store, edges = _run_divergence()
    assert len(edges) == 1, "a shared-space divergence commits"
    assert store.evidence.list_for_subject(SUBJECT, space_id=SHARED)


# --- 10/11. axes stay separate; ordering is deterministic --------------------


def test_attribution_and_support_axes_remain_separate():
    """A divergence edge touches neither lineage attribution nor support."""
    store, edges = _run_divergence()
    assert store.lineages.list_for_subject(SUBJECT, space_id=SHARED) == []
    assert all(
        not hasattr(e, "support") and not hasattr(e, "attribution") for e in edges
    )


def test_candidate_ordering_is_deterministic():
    def offered() -> list[str]:
        appraiser = _CapturesThenDiverges(propose=False)
        service, _ = _service(appraiser)
        for source in ("pA", "pB", "pC"):
            service.record_interaction(
                SUBJECT, [_account(f"account from {source}", source)], space_id=SHARED
            )
        return [str(c.handle) for c in appraiser.requests[-1].divergence_candidates]

    first, second = offered(), offered()
    assert first == second
    assert first == sorted(first), "presentation order is ascending (rule 10)"
