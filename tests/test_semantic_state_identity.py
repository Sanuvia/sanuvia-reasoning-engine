"""Deterministic identity adjudication and the integrity foundation.

Technical Design v1.5.4 §2 G (deterministic arm), §2 H (R1a), §2 B/§2 J.1
(handles, R7), §3.2 (complete-plan validation), §3.1/§5.3/§5.5 (atomicity).

Scope: these cover the **deterministic** identity arm only. The R1 model-assisted
resolver remains Slice 2, so ``REFINE_EXISTING`` is not reachable here and is
asserted unreachable rather than skipped.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support.deterministic import SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.reasoning import CoreLoop
from sanuvia.application.ports.reasoning import (
    Appraisal,
    Bearing,
    BearingKind,
    CandidateProposal,
    CommitmentSignatureView,
    DivergenceProposal,
    EvidenceHandle,
    HypothesisHandle,
    ProposedHypothesis,
)
from sanuvia.application.reasoning.handles import (
    MAX_DIVERGENCE_CANDIDATES,
    HandleTable,
    build_divergence_candidates,
    build_table,
)
from sanuvia.application.reasoning.identity import (
    DeterministicAdjudicator,
    LineageView,
)
from sanuvia.application.reasoning.plan_validation import (
    AppraisedObservation,
    RevisionPlan,
    normalise_statement,
    validate_plan,
)
from sanuvia.application.reasoning.unit_of_work import UnitOfWork, bundle_stores
from sanuvia.domain import (
    ClaimClass,
    CommitmentSignature,
    DependencyEdge,
    DependencyRelation,
    EvidenceClass,
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceRole,
    EvidenceSourceKind,
    EvidenceStanding,
    EvidenceSubjectKind,
    DEFAULT_SPACE_ID,
    FutureTrajectory,
    GovernedOutcome,
    GovernedRejection,
    HypothesisId,
    IdentityOutcome,
    Provenance,
    RevisionEvent,
    SourceObservationRef,
    SpaceKind,
    Stance,
    StatementVersion,
    SubjectId,
    TrajectoryKind,
    canonical_divergence_pair,
)
from sanuvia.domain.revision import RevisionOutcome, RevisionStatus
from sanuvia.domain.uncertainty import (
    ClassificationConfidence,
    EvidenceReliability,
    ProvenanceConfidence,
)

SHARED = "space:shared:dyad-1"
STMT = "Person 1 will use a negative response to the promotion as a signal to plan their exit."


# --- fixtures ----------------------------------------------------------------


def _record(
    n: int,
    *,
    role: EvidenceRole = EvidenceRole.ACCOUNT,
    source: str = "pA",
    subject: str = "pX",
    subject_kind: EvidenceSubjectKind = EvidenceSubjectKind.PARTICIPANT,
    source_kind: EvidenceSourceKind = EvidenceSourceKind.PARTICIPANT,
    space: str = SHARED,
    k: int = 0,
) -> EvidenceRecord:
    return EvidenceRecord(
        id=f"evidence-{n}",
        subject_id="subject-1",
        evidence_class=EvidenceClass.NARRATIVE,
        content=f"observation {n}",
        provenance=Provenance(source="extractor:x", confidence=ProvenanceConfidence(1.0)),
        reliability=EvidenceReliability(0.8),
        classification_confidence=ClassificationConfidence(0.9),
        occurred_at=datetime.now(timezone.utc),
        space_id=space,
        source_ref=SourceObservationRef("case-001", 1, k),
        standing=EvidenceStanding(
            source_kind=source_kind,
            subject_kind=subject_kind,
            role=role,
            source_id=source if source_kind is EvidenceSourceKind.PARTICIPANT else None,
            subject_id=subject
            if subject_kind
            in (EvidenceSubjectKind.PARTICIPANT, EvidenceSubjectKind.THIRD_PARTY)
            else None,
        ),
    )


def _sig(stance: Stance = Stance.AFFIRMS, cc: ClaimClass = ClaimClass.INTENTION) -> CommitmentSignature:
    return CommitmentSignature(
        subject="pA", attribution="sanuvia working reading", claim_class=cc, stance=stance
    )


def _view(stance: Stance = Stance.AFFIRMS, cc: ClaimClass = ClaimClass.INTENTION,
          label: str = "r1::P1") -> CommitmentSignatureView:
    return CommitmentSignatureView(
        subject=label, attribution="sanuvia working reading", claim_class=cc, stance=stance
    )


def _version(stmt: str, n: int = 1, *, cc: ClaimClass = ClaimClass.INTENTION,
             stance: Stance = Stance.AFFIRMS) -> StatementVersion:
    return StatementVersion(
        id=f"sv-{n}", hypothesis_id="hyp-1", statement=stmt,
        claim_class=cc, stance=stance, created_at_version="wm-1",
    )


def _lineage(versions, stance: Stance = Stance.AFFIRMS) -> dict:
    """One retrieval bound holding ONE lineage.

    The bound maps to a list because it admits several lineages (M-2); this
    helper is the single-lineage case.
    """
    sig = _sig()
    key = (str(sig.subject), sig.attribution)
    return {key: [LineageView(hypothesis_id="hyp-1", key=key,
                              current_stance=stance, versions=tuple(versions))]}


# --- committed-state matching -----------------------------------------------


def test_exact_duplicate_of_committed_resolves_match_existing():
    """Locked §3.3: an exact duplicate is MATCH_EXISTING and creates no identity."""
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", STMT, _view()), _sig(),
        committed=_lineage([_version(STMT)]), in_flight={},
    )
    assert d.outcome is IdentityOutcome.MATCH_EXISTING
    assert d.matched_hypothesis_id == "hyp-1"
    assert d.matched_in_flight is False


@pytest.mark.parametrize("variant", [
    "  " + STMT + "  ", STMT.upper(), STMT.rstrip(".") , STMT.replace(" ", "  "),
])
def test_normalisation_is_case_whitespace_and_terminal_punctuation_only(variant):
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", variant, _view()), _sig(),
        committed=_lineage([_version(STMT)]), in_flight={},
    )
    assert d.outcome is IdentityOutcome.MATCH_EXISTING


def test_normalisation_does_not_conflate_different_statements():
    """Normalisation must not become a similarity heuristic."""
    assert normalise_statement("a b") != normalise_statement("a c")
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", "an entirely different reading", _view()), _sig(),
        committed=_lineage([_version(STMT)]), in_flight={},
    )
    assert d.outcome is not IdentityOutcome.MATCH_EXISTING


# --- statement-history comparison (F-2) --------------------------------------


def test_earlier_statement_version_still_identifies_the_lineage():
    """F-2: exact match runs against EVERY StatementVersion, not only the current.

    A statement that was exact at any accepted version still identifies the
    lineage, which is what stops a re-presented earlier statement founding a
    duplicate after a later refinement.
    """
    versions = [
        _version("the original reading", 1),
        _version("the sharpened reading", 2, cc=ClaimClass.BEHAVIOUR_PATTERN),
    ]
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", "the original reading", _view()), _sig(),
        committed=_lineage(versions), in_flight={},
    )
    assert d.outcome is IdentityOutcome.MATCH_EXISTING


def test_retrieval_is_bounded_on_the_immutable_pair_only():
    """F-2: claim_class is versioned and must not bound retrieval.

    A candidate proposing the refinement §2 H calls legitimate must still
    retrieve its own lineage rather than falling through to DISTINCT_NEW.
    """
    sig = _sig(cc=ClaimClass.BEHAVIOUR_PATTERN)  # claim_class differs from the lineage
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", "a sharpened wording", _view(cc=ClaimClass.BEHAVIOUR_PATTERN)),
        sig, committed=_lineage([_version("the original reading")]), in_flight={},
    )
    # Retrieved (not DISTINCT_NEW), and parked because no resolver is configured.
    assert d.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    assert d.plausible_matches == ("hyp-1",)


# --- in-flight matching (the Run 002 pattern) --------------------------------


def test_in_flight_duplicate_within_one_uncommitted_plan_matches():
    """The Run 002 pattern: separate appraisal calls, one interaction, nothing
    committed yet. A rule scoped only to committed state cannot see these."""
    sig = _sig()
    key = (str(sig.subject), sig.attribution)
    in_flight = {key: [LineageView(hypothesis_id=None, key=key,
                                   current_stance=Stance.AFFIRMS, in_flight=True,
                                   in_flight_statement=STMT,
                                   in_flight_signature=sig)]}
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c2", STMT, _view()), sig, committed={}, in_flight=in_flight,
    )
    assert d.outcome is IdentityOutcome.MATCH_EXISTING
    assert d.matched_in_flight is True
    assert d.matched_hypothesis_id is None  # no durable id yet (F-16)
    assert d.matched_lineage_key == key


def test_distinct_new_when_no_lineage_is_retrievable():
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", "a genuinely new reading", _view()), _sig(),
        committed={}, in_flight={},
    )
    assert d.outcome is IdentityOutcome.DISTINCT_NEW
    assert d.matched_hypothesis_id is None


def test_plurality_is_preserved_for_genuinely_distinct_readings():
    """Locked §3.4: one evidence item may support multiple distinct explanations.
    'Revision first' is a burden-of-distinctness rule, not a ban on plurality."""
    a = DeterministicAdjudicator()
    d1 = a.adjudicate(CandidateProposal("c1", "reading one", _view()), _sig(),
                      committed={}, in_flight={})
    other = CommitmentSignature(subject="pB", attribution="participant account",
                                claim_class=ClaimClass.INTERPRETATION, stance=Stance.AFFIRMS)
    d2 = a.adjudicate(CandidateProposal("c2", "reading two", _view()), other,
                      committed={}, in_flight={})
    assert d1.outcome is d2.outcome is IdentityOutcome.DISTINCT_NEW


# --- unresolved comparison while R1 is unconfigured --------------------------


def test_plausible_but_inexact_parks_when_no_resolver_is_configured():
    """§2 G: park rather than commit on an unmade judgement.

    The candidate is NOT discarded: the decision preserves the plausible matches
    and the rationale so a durable IdentityAdjudication can be written.
    """
    a = DeterministicAdjudicator()
    assert a.has_resolver is False
    d = a.adjudicate(
        CandidateProposal("c1", "a paraphrase of the same commitment", _view()), _sig(),
        committed=_lineage([_version(STMT)]), in_flight={},
    )
    assert d.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    assert d.plausible_matches == ("hyp-1",)
    assert d.rationale and "Slice 2" in d.rationale


def test_refine_existing_is_unreachable_on_the_deterministic_arm():
    """R1 remains Slice 2, so REFINE_EXISTING cannot be produced here.

    Asserted rather than skipped: a deterministic REFINE_EXISTING would mean the
    resolver had been silently replaced by a heuristic.
    """
    a = DeterministicAdjudicator()
    seen = set()
    for stmt in [STMT, "paraphrase of it", "something else entirely", ""]:
        if not stmt:
            continue
        for committed in (_lineage([_version(STMT)]), {}):
            seen.add(a.adjudicate(CandidateProposal("c", stmt, _view()), _sig(),
                                  committed=committed, in_flight={}).outcome)
    assert IdentityOutcome.REFINE_EXISTING not in seen


# --- R1a: stance inversion is not refinement ---------------------------------


def test_stance_inversion_never_merges_into_the_lineage():
    """§2 H / R1a: two opposed commitments may not share one hypothesis_id.

    Note on mechanism: this passes via signature equality, not via the R1a guard
    in the adjudicator. Exact match requires an equal signature, and the
    signature includes stance, so an inverted-stance candidate can never reach
    the guard through valid data. The guard is tested separately below.
    """
    inverted = _sig(stance=Stance.NEGATES)
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", STMT, _view(stance=Stance.NEGATES)), inverted,
        committed=_lineage([_version(STMT)], stance=Stance.AFFIRMS), in_flight={},
    )
    assert d.outcome is not IdentityOutcome.MATCH_EXISTING
    assert d.outcome is not IdentityOutcome.REFINE_EXISTING
    assert d.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED


def test_open_stance_never_inverts():
    """N-8: inversion is affirms <-> negates only."""
    from sanuvia.domain import inverts
    assert inverts(Stance.AFFIRMS, Stance.NEGATES)
    assert inverts(Stance.NEGATES, Stance.AFFIRMS)
    assert not inverts(Stance.OPEN, Stance.AFFIRMS)
    assert not inverts(Stance.AFFIRMS, Stance.OPEN)
    assert not inverts(Stance.OPEN, Stance.OPEN)
    assert not inverts(Stance.AFFIRMS, Stance.AFFIRMS)


# --- durable identity is engine-owned ----------------------------------------


def test_candidate_proposal_carries_no_durable_identity():
    """Locked §3.3/§3.1: the model proposes language, never identity or support.

    The set equality is deliberate and stays exact: it is the mutation guard.
    Any field added to ``CandidateProposal`` must be added here too, which
    forces the question "does this let the model propose identity or support?"
    to be answered in review rather than by omission.

    ``predicted_trajectory`` (errata E-1) is admitted as **content only**. The
    assertions below are what make that claim testable rather than asserted:
    it is optional, it defaults to absent, and it is a description -- it names
    no hypothesis and carries no support value.
    """
    fields = set(CandidateProposal.__dataclass_fields__)
    assert fields == {"local_ref", "statement", "signature", "predicted_trajectory"}
    assert "hypothesis_id" not in fields
    assert "initial_support" not in fields
    assert "supporting_evidence_ids" not in fields

    # Content only: optional, absent by default, and identity/support free.
    bare = CandidateProposal("c1", "a new reading", _view())
    assert bare.predicted_trajectory is None

    carried = CandidateProposal(
        "c1", "a new reading", _view(),
        predicted_trajectory=FutureTrajectory(
            TrajectoryKind.RECURRING_CYCLE, "distance then repair"
        ),
    )
    traj_fields = set(type(carried.predicted_trajectory).__dataclass_fields__)
    assert "hypothesis_id" not in traj_fields
    assert "support" not in traj_fields and "initial_support" not in traj_fields


def test_trajectory_on_a_proposal_cannot_create_a_prediction():
    """Errata E-1: the carrier is content, so it must not reach the gate.

    A trajectory hint is recorded against a lineage but read only by
    ``_regenerate_predictions`` *after* ``prediction_support_threshold`` has
    already admitted the hypothesis. A sub-threshold lineage carrying a hint
    therefore yields no prediction -- if this ever passes, the hint has become
    a support-bearing input and R6 is no longer the sole source of support.
    """
    evidence = _record(1, space=DEFAULT_SPACE_ID)  # reliability 0.8
    script = {
        EvidenceRecordId(evidence.id): Appraisal(
            proposals=(
                ProposedHypothesis(
                    HypothesisId("H_t"), "a recurring cycle", 0.95, (),
                    predicted_trajectory=FutureTrajectory(
                        TrajectoryKind.RECURRING_CYCLE, "distance then repair"
                    ),
                ),
            )
        )
    }
    deps = build_in_memory_dependencies(
        appraiser=ScriptedAppraiser(script), ids=SequentialIdGenerator()
    )
    subject = SubjectId(evidence.subject_id)
    result = CoreLoop(deps).ingest(subject, [evidence])

    # R6 derives 0.4 from reliability alone; the authored 0.95 is not consulted.
    assert [h.support.value for h in deps.hypotheses.list_for_subject(subject)] == [0.4]
    assert result.predictions == (), "a trajectory hint must not cross the gate"


def test_no_durable_id_is_issued_by_adjudication_itself():
    """Durable ids are issued after adjudication, by the engine -- not here."""
    ids = SequentialIdGenerator()
    before = dict(ids._counters)
    DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", "a new reading", _view()), _sig(),
        committed={}, in_flight={},
    )
    assert dict(ids._counters) == before  # adjudication allocated nothing


def test_bearing_kind_cannot_express_divergence():
    """M-01: divergence is evidence<->evidence and cannot name a hypothesis."""
    assert not any(k.name == "DIVERGES_WITH" for k in BearingKind)


# --- R7 candidate set and Q4 -------------------------------------------------


def test_candidate_set_is_bounded_to_eight_most_recent():
    obs = _record(100, source="pA")
    pool = [_record(i, source="pB") for i in range(1, 13)]
    got = build_divergence_candidates(observation=obs, admitted=pool)
    assert len(got) == MAX_DIVERGENCE_CANDIDATES
    assert {int(str(r.id).split("-")[1]) for r in got} == set(range(5, 13))


@pytest.mark.parametrize("kwargs,why", [
    ({"source": "pA"}, "same participant"),
    ({"source": "pB", "subject_kind": EvidenceSubjectKind.DYAD}, "dyad excluded"),
    ({"source": "pB", "subject_kind": EvidenceSubjectKind.THIRD_PARTY}, "third party excluded"),
    ({"source": "pB", "role": EvidenceRole.EVENT_OBSERVATION}, "not an account"),
    ({"source": "pB", "source_kind": EvidenceSourceKind.EXTERNAL_SOURCE}, "not a participant source"),
])
def test_ineligible_candidates_are_never_offered(kwargs, why):
    obs = _record(100, source="pA")
    assert build_divergence_candidates(observation=obs, admitted=[_record(1, **kwargs)]) == (), why


def test_already_recorded_pair_is_excluded_before_disclosure():
    """Q4 / rule 6b: nothing is disclosed for an already-recorded pair."""
    obs, other = _record(100, source="pA"), _record(1, source="pB")
    pair = tuple(sorted((str(obs.id), str(other.id))))
    assert build_divergence_candidates(
        observation=obs, admitted=[other], existing_pairs=frozenset({pair})
    ) == ()


def test_non_appraisable_observation_gets_no_candidate_set():
    """Q1: a resonance record is never appraised, so it proposes no divergence."""
    obs = _record(100, source="pA", role=EvidenceRole.RESPONSE_OR_RESONANCE)
    assert build_divergence_candidates(observation=obs, admitted=[_record(1, source="pB")]) == ()


# --- handles -----------------------------------------------------------------


def test_handles_expose_no_canonical_or_durable_identifiers():
    """TD-V1: no EvidenceRecordId, HypothesisId or ParticipantId in handle space."""
    obs = _record(100, source="pA")
    cands = [_record(1, source="pB")]
    t = build_table(request_id="req-1", observation=obs, active_hypotheses=[],
                    candidates=cands, participants=["pA", "pB"])
    for h in list(t.divergence_candidates) + list(t.hypotheses) + list(t.participants):
        assert "evidence-" not in h and "hyp-" not in h
        assert h.startswith("req-1::")


def test_cross_request_handle_is_distinguishable_from_never_issued():
    """TD-13d: the two failures must be told apart in the audit."""
    obs = _record(100, source="pA")
    t = build_table(request_id="req-1", observation=obs, active_hypotheses=[],
                    candidates=[_record(1, source="pB")], participants=["pA"])
    assert t.classify_unknown_evidence_handle("req-2::E1") == "cross-request"
    assert t.classify_unknown_evidence_handle("E99") == "never-issued"
    with pytest.raises(GovernedRejection) as e:
        t.resolve_divergence_candidate("req-2::E1")
    assert e.value.outcome is GovernedOutcome.UNKNOWN_EVIDENCE_REFERENCE


# --- atomicity ---------------------------------------------------------------


def _ledger_event(n: int) -> RevisionEvent:
    return RevisionEvent(
        id=f"rev-{n}", subject_id="subject-1", affected_object_id="hyp-1",
        outcome=RevisionOutcome.STRENGTHEN, triggering_evidence_ids=("evidence-1",),
        status=RevisionStatus.COMMITTED, created_at=datetime.now(timezone.utc),
        to_model_version_id="wm-1",
    )


def test_every_store_in_the_bundle_is_snapshotable():
    """§5.1 / N-1: coverage follows the bundle, not a fixed count."""
    stores = bundle_stores(InMemoryReasoningStore())
    assert stores, "bundle must not be empty"
    for name, store in stores.items():
        assert hasattr(store, "snapshot") and hasattr(store, "restore"), name


def test_nested_ledger_container_is_restored_to_depth():
    """F-9: the ledger is a dict of lists and ``append`` mutates an inner list.

    A shallow dict() copy would share those lists and silently fail to roll back,
    which is the defect this test exists to catch.
    """
    store = InMemoryReasoningStore()
    store.ledger.append(_ledger_event(1))
    uow = UnitOfWork(stores=bundle_stores(store), ids=SequentialIdGenerator())
    uow.begin()
    store.ledger.append(_ledger_event(2))
    assert len(store.ledger.read("subject-1")) == 2
    uow.restore()
    assert len(store.ledger.read("subject-1")) == 1


def test_rejection_restores_identifier_counters_including_pre_mutation():
    """TD-13c / F-4 / F-6: restore() runs on EVERY rejection.

    Canonical evidence ids are minted before any store write, so a plan rejected
    at a validation check must still reinstate the counters -- otherwise the next
    interaction's ids differ from what they would have been.
    """
    store, ids = InMemoryReasoningStore(), SequentialIdGenerator()
    uow = UnitOfWork(stores=bundle_stores(store), ids=ids)
    uow.begin()
    assert ids.new_id("evidence") == "evidence-1"
    assert ids.new_id("evidence") == "evidence-2"
    uow.restore()  # pre-mutation rejection: nothing was written
    assert ids.new_id("evidence") == "evidence-1"


def test_hold_closes_with_commit_not_restore():
    """§3.6: the hold completed; it has nothing to undo.

    restore() carries rejection semantics and would blur the
    NO_EVIDENCE_HOLD / REJECTED_PLAN distinction §5.7 depends on.
    """
    store, ids = InMemoryReasoningStore(), SequentialIdGenerator()
    uow = UnitOfWork(stores=bundle_stores(store), ids=ids)
    uow.begin()
    uow.commit()
    assert uow.is_open is False
    assert ids.new_id("evidence") == "evidence-1"


def test_statement_version_history_is_append_only_and_restorable():
    store = InMemoryReasoningStore()
    store.statement_versions.append(_version("first", 1))
    uow = UnitOfWork(stores=bundle_stores(store), ids=SequentialIdGenerator())
    uow.begin()
    store.statement_versions.append(_version("second", 2))
    assert len(store.statement_versions.history("hyp-1")) == 2
    uow.restore()
    hist = store.statement_versions.history("hyp-1")
    assert len(hist) == 1 and hist[0].statement == "first"


# --- integration with complete-plan validation -------------------------------


def _table(hyps=None, participants=("pA",)):
    obs = _record(1)
    base = build_table(request_id="r1", observation=obs, active_hypotheses=[],
                       candidates=[], participants=list(participants))
    return HandleTable(request_id="r1", observation=base.observation,
                       observation_id=obs.id, hypotheses=hyps or {},
                       participants=base.participants)


def _plan(obs_record, **kw):
    t = kw.pop("table", None) or _table()
    o = AppraisedObservation(evidence_id=obs_record.id, table=t, raw_response="{}", **kw)
    return RevisionPlan(subject_id="subject-1", space_id=SHARED,
                        admitted=(obs_record,), appraised=(o,))


def test_adjudicated_decisions_satisfy_check_3a():
    """Check 3a: every candidate reaches validation with an IdentityDecision."""
    rec = _record(1)
    t = _table()
    label = next(iter(t.participants))
    prop = CandidateProposal("c1", "a reading", _view(label=label))
    d = DeterministicAdjudicator().adjudicate(prop, _sig(), committed={}, in_flight={})
    plan = _plan(rec, table=t, proposals=(prop,),
                 decisions={prop.local_ref: (d.outcome.value, d.matched_hypothesis_id)})
    validate_plan(plan, committed_evidence={}, active_hypotheses={})


def test_missing_identity_decision_is_an_adjudication_order_breach():
    rec = _record(1)
    t = _table()
    label = next(iter(t.participants))
    plan = _plan(rec, table=t,
                 proposals=(CandidateProposal("c1", "a reading", _view(label=label)),))
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={})
    assert e.value.outcome is GovernedOutcome.NON_ATOMIC_REVISION_PLAN
    assert e.value.breach_kind.value == "ADJUDICATION_ORDER"
    assert e.value.breach_kind.value != "COMMIT_ATOMICITY"  # no failing write implied


def test_duplicate_proposals_in_one_response_are_rejected():
    """Locked §3.10: DUPLICATE_HYPOTHESIS_PROPOSAL, scoped to one appraisal."""
    rec, t = _record(1), _table()
    label = next(iter(t.participants))
    props = (CandidateProposal("c1", "Same  statement.", _view(label=label)),
             CandidateProposal("c2", "same statement", _view(label=label)))
    plan = _plan(rec, table=t, proposals=props,
                 decisions={p.local_ref: ("DISTINCT_NEW", None) for p in props})
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={})
    assert e.value.outcome is GovernedOutcome.DUPLICATE_HYPOTHESIS_PROPOSAL


def test_bearing_plus_match_existing_on_one_observation_is_rejected():
    """Check 2(f) / D-1: the bearing + MATCH_EXISTING conflict, over the plan."""
    rec = _record(1)
    t = _table(hyps={HypothesisHandle("r1::H1"): "hyp-1"})
    label = next(iter(t.participants))
    prop = CandidateProposal("c1", "a reading", _view(label=label))
    plan = _plan(rec, table=t,
                 bearings=(Bearing(HypothesisHandle("r1::H1"), BearingKind.CONTRADICTS),),
                 proposals=(prop,),
                 decisions={"c1": ("MATCH_EXISTING", "hyp-1")})
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={"hyp-1": object()})
    assert e.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert e.value.boundary.value == "APPRAISAL"


def test_supports_plus_match_existing_is_not_rejected_by_check_2f():
    """F-3: redundant agreement is recorded, not an error. Only WEAKENS and
    CONTRADICTS conflict with a MATCH_EXISTING attachment."""
    rec = _record(1)
    t = _table(hyps={HypothesisHandle("r1::H1"): "hyp-1"})
    label = next(iter(t.participants))
    plan = _plan(rec, table=t,
                 bearings=(Bearing(HypothesisHandle("r1::H1"), BearingKind.SUPPORTS),),
                 proposals=(CandidateProposal("c1", "a reading", _view(label=label)),),
                 decisions={"c1": ("MATCH_EXISTING", "hyp-1")})
    validate_plan(plan, committed_evidence={}, active_hypotheses={"hyp-1": object()})


def test_inverted_stance_without_contradicts_bearing_fails_check_10():
    """Q5: the deterministic structural case only -- no prose or NLU detector."""
    rec = _record(1)
    t = _table(hyps={HypothesisHandle("r1::H1"): "hyp-1"})
    label = next(iter(t.participants))
    prop = CandidateProposal("c1", "an opposed reading", _view(stance=Stance.NEGATES, label=label))
    plan = _plan(rec, table=t, proposals=(prop,), decisions={"c1": ("DISTINCT_NEW", None)})
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={"hyp-1": object()},
                      lineage_stance={"hyp-1": Stance.AFFIRMS},
                      lineage_key_index={(str(t.participants[label]), "sanuvia working reading"): "hyp-1"})
    assert e.value.outcome is GovernedOutcome.INVALID_CONTRADICTION_PLAN


def test_inverted_stance_with_contradicts_bearing_passes_check_10():
    rec = _record(1)
    t = _table(hyps={HypothesisHandle("r1::H1"): "hyp-1"})
    label = next(iter(t.participants))
    prop = CandidateProposal("c1", "an opposed reading", _view(stance=Stance.NEGATES, label=label))
    plan = _plan(rec, table=t, proposals=(prop,),
                 bearings=(Bearing(HypothesisHandle("r1::H1"), BearingKind.CONTRADICTS),),
                 decisions={"c1": ("DISTINCT_NEW", None)})
    validate_plan(plan, committed_evidence={}, active_hypotheses={"hyp-1": object()},
                  lineage_stance={"hyp-1": Stance.AFFIRMS},
                  lineage_key_index={(str(t.participants[label]), "sanuvia working reading"): "hyp-1"})


def test_resonance_record_may_trigger_no_operation():
    """Q1 backstop in check 9. The structural closure is that no appraisal call
    is made at all; this guards an internally constructed plan."""
    rec = _record(1, role=EvidenceRole.RESPONSE_OR_RESONANCE)
    t = _table(hyps={HypothesisHandle("r1::H1"): "hyp-1"})
    plan = _plan(rec, table=t,
                 bearings=(Bearing(HypothesisHandle("r1::H1"), BearingKind.SUPPORTS),))
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={"hyp-1": object()})
    assert e.value.outcome is GovernedOutcome.EVIDENCE_ROLE_VIOLATION


def test_re_admission_under_a_different_role_is_an_upgrade_violation():
    """Check 9(a) structural trigger (F-6, N-2): same SourceObservationRef, two
    roles. A participant reporting an EVENT_OBSERVATION about another
    participant is legitimate and must NOT be the trigger."""
    a = _record(1, role=EvidenceRole.ACCOUNT, k=0)
    b = _record(2, role=EvidenceRole.EVENT_OBSERVATION, k=0)  # same source_ref
    plan = RevisionPlan(subject_id="subject-1", space_id=SHARED, admitted=(a, b),
                        appraised=(AppraisedObservation(evidence_id=a.id, table=_table(),
                                                        raw_response="{}"),))
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={})
    assert e.value.outcome is GovernedOutcome.ACCOUNT_ROLE_UPGRADE_VIOLATION


def test_participant_reporting_an_event_about_another_is_legitimate():
    """The converse of the rule above: this must NOT be rejected."""
    rec = _record(1, role=EvidenceRole.EVENT_OBSERVATION, source="pA", subject="pB")
    validate_plan(_plan(rec), committed_evidence={}, active_hypotheses={})


# --- divergence plan integrity ----------------------------------------------


def _edge(a: str, b: str) -> DependencyEdge:
    lo, hi = canonical_divergence_pair(a, b)
    return DependencyEdge(id="dep-1", from_ref=lo, to_ref=hi,
                          relation=DependencyRelation.DIVERGES_WITH,
                          created_at=datetime.now(timezone.utc))


def test_valid_divergence_pair_passes():
    a, b = _record(1, source="pA"), _record(2, source="pB")
    plan = RevisionPlan(subject_id="subject-1", space_id=SHARED, admitted=(a, b),
                        edges=(_edge(str(a.id), str(b.id)),))
    validate_plan(plan, committed_evidence={}, active_hypotheses={}, space_kind=SpaceKind.SHARED)


def test_divergence_endpoint_from_a_personal_space_is_rejected():
    """Check 8b / §2 J.2 D1: no cross-space or PERSONAL account content."""
    a = _record(1, source="pA")
    b = _record(2, source="pB", space="space:personal:pB")
    plan = RevisionPlan(subject_id="subject-1", space_id=SHARED, admitted=(a, b),
                        edges=(_edge(str(a.id), str(b.id)),))
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={})
    assert e.value.outcome is GovernedOutcome.INVALID_DIVERGENCE_PLAN


def test_divergence_requires_a_shared_space():
    a, b = _record(1, source="pA"), _record(2, source="pB")
    plan = RevisionPlan(subject_id="subject-1", space_id=SHARED, admitted=(a, b),
                        edges=(_edge(str(a.id), str(b.id)),))
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={},
                      space_kind=SpaceKind.PERSONAL)
    assert e.value.outcome is GovernedOutcome.INVALID_DIVERGENCE_PLAN


def test_divergence_edge_must_be_canonically_ordered():
    """Symmetry is guaranteed by construction; the domain refuses the rest."""
    from sanuvia.domain import InvariantViolation
    with pytest.raises(InvariantViolation):
        DependencyEdge(id="dep-1", from_ref="evidence-9", to_ref="evidence-2",
                       relation=DependencyRelation.DIVERGES_WITH,
                       created_at=datetime.now(timezone.utc))


def test_divergence_endpoints_must_be_different_participants():
    a, b = _record(1, source="pA"), _record(2, source="pA")
    plan = RevisionPlan(subject_id="subject-1", space_id=SHARED, admitted=(a, b),
                        edges=(_edge(str(a.id), str(b.id)),))
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={},
                      space_kind=SpaceKind.SHARED)
    assert e.value.outcome is GovernedOutcome.INVALID_DIVERGENCE_PLAN


def test_divergence_endpoint_must_be_a_participant_account():
    a = _record(1, source="pA")
    b = _record(2, source="pB", role=EvidenceRole.EVENT_OBSERVATION)
    plan = RevisionPlan(subject_id="subject-1", space_id=SHARED, admitted=(a, b),
                        edges=(_edge(str(a.id), str(b.id)),))
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={},
                      space_kind=SpaceKind.SHARED)
    assert e.value.outcome is GovernedOutcome.INVALID_DIVERGENCE_PLAN


# --- source-ref round trip ---------------------------------------------------


def test_source_observation_ref_round_trips_including_within_interaction_index():
    """TD-03: the within-interaction index is what Run 002 lost."""
    recs = [_record(n, k=k) for n, k in ((1, 0), (2, 1), (3, 2))]
    index = {r.source_ref: r.id for r in recs}
    assert len(index) == 3, "three observations in one interaction must be distinguishable"
    for r in recs:
        assert index[r.source_ref] == r.id
        back = next(ref for ref, eid in index.items() if eid == r.id)
        assert back == r.source_ref


def test_source_ref_mapping_conflict_is_a_governed_failure():
    rec = _record(1, k=0)
    plan = RevisionPlan(subject_id="subject-1", space_id=SHARED, admitted=(rec,))
    with pytest.raises(GovernedRejection) as e:
        validate_plan(plan, committed_evidence={}, active_hypotheses={},
                      source_ref_index={rec.source_ref: "evidence-999"})
    assert e.value.outcome is GovernedOutcome.SOURCE_REFERENCE_MAPPING_FAILURE


# --- governed outcome vocabulary --------------------------------------------


def test_governed_outcome_set_is_exactly_fourteen():
    """Thirteen from locked §3.10 plus INVALID_APPRAISAL_RESPONSE under R8."""
    assert len(list(GovernedOutcome)) == 14
    assert GovernedOutcome.INVALID_APPRAISAL_RESPONSE in set(GovernedOutcome)


def test_discriminators_are_required_where_the_design_requires_them():
    from sanuvia.domain import InvariantViolation
    with pytest.raises(InvariantViolation):
        GovernedRejection(GovernedOutcome.INVALID_APPRAISAL_RESPONSE, "x")
    with pytest.raises(InvariantViolation):
        GovernedRejection(GovernedOutcome.NON_ATOMIC_REVISION_PLAN, "x")


def test_r1a_guard_blocks_a_merge_if_exact_match_is_ever_reached():
    """The defensive half of R1a, reached only through an invalid lineage.

    A lineage can never invert its own stance in valid data -- the only way to
    append a version is REFINE_EXISTING and R1a forbids stance inversion as
    refinement -- so this constructs that impossible state deliberately to prove
    the guard fires rather than silently merging two opposed commitments.

    Without this test the guard is unreachable and a mutation that removes it
    goes undetected.
    """
    sig = _sig(stance=Stance.AFFIRMS)
    key = (str(sig.subject), sig.attribution)
    # Impossible by construction: a historical AFFIRMS version under a lineage
    # whose current stance is NEGATES.
    corrupt = {key: [LineageView(hypothesis_id="hyp-1", key=key,
                                 current_stance=Stance.NEGATES,
                                 versions=(_version(STMT, stance=Stance.AFFIRMS),))]}
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", STMT, _view(stance=Stance.AFFIRMS)), sig,
        committed=corrupt, in_flight={},
    )
    assert d.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    assert d.outcome is not IdentityOutcome.MATCH_EXISTING
    assert d.rationale and "R1a" in d.rationale


# --- M-2: a retrieval bound admits MANY lineages -----------------------------


def _lineages(*statements, stance: Stance = Stance.AFFIRMS) -> dict:
    """One retrieval bound holding SEVERAL distinct lineages."""
    sig = _sig()
    key = (str(sig.subject), sig.attribution)
    return {
        key: [
            LineageView(hypothesis_id=f"hyp-{i}", key=key, current_stance=stance,
                        versions=(_version(stmt),))
            for i, stmt in enumerate(statements, start=1)
        ]
    }


def test_several_lineages_can_share_one_retrieval_bound():
    """M-2: the bound is (subject, attribution), which many commitments share.

    ``subject`` and ``attribution`` are a voice-and-person pair, so every
    distinct commitment one voice holds about one person lands on the same
    key. A mapping of one lineage per key silently discarded all but the last.
    """
    committed = _lineages("the first reading", "the second reading",
                          "the third reading")
    key = next(iter(committed))
    assert len(committed[key]) == 3


@pytest.mark.parametrize("target,expected", [
    ("the first reading", "hyp-1"),
    ("the second reading", "hyp-2"),
    ("the third reading", "hyp-3"),
])
def test_exact_match_finds_any_lineage_under_a_shared_bound(target, expected):
    """M-2: the match may be against ANY admitted lineage, not just the last.

    Before the fix only one lineage survived retrieval, so a candidate exactly
    matching either of the others fell through to a park -- founding a
    duplicate of a commitment the system already held.
    """
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", target, _view()), _sig(),
        committed=_lineages("the first reading", "the second reading",
                            "the third reading"),
        in_flight={},
    )
    assert d.outcome is IdentityOutcome.MATCH_EXISTING
    assert d.matched_hypothesis_id == expected


def test_an_earlier_candidate_is_not_overwritten_by_a_later_one():
    """M-2 as stated: do not overwrite an earlier candidate sharing the bound.

    The first lineage must remain retrievable after a second is added under
    the same key.
    """
    committed = _lineages("the first reading", "the second reading")
    first = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", "the first reading", _view()), _sig(),
        committed=committed, in_flight={},
    )
    assert first.matched_hypothesis_id == "hyp-1", "the earlier lineage survived"


def test_parking_preserves_every_plausible_match_not_merely_the_first():
    """M-2: the parked record must carry the full ambiguity that caused it.

    Recording one plausible match would hide the very ambiguity being
    referred: reviewing a parked candidate needs every lineage it might
    belong to.
    """
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", "an unrelated new reading", _view()), _sig(),
        committed=_lineages("the first reading", "the second reading",
                            "the third reading"),
        in_flight={},
    )
    assert d.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    assert d.plausible_matches == ("hyp-1", "hyp-2", "hyp-3")
    assert d.rationale and "3 plausible lineage(s)" in d.rationale


def test_retrieval_order_is_deterministic_across_repeated_adjudications():
    """M-2: retrieval must not depend on iteration accident."""
    committed = _lineages("the first reading", "the second reading",
                          "the third reading")
    outcomes = [
        DeterministicAdjudicator().adjudicate(
            CandidateProposal("c1", "an unrelated new reading", _view()), _sig(),
            committed=committed, in_flight={},
        ).plausible_matches
        for _ in range(5)
    ]
    assert len(set(outcomes)) == 1, "retrieval order varied between runs"


def test_committed_arm_is_searched_before_the_in_flight_arm():
    """§2 G resolution order: committed state first, then in-flight."""
    sig = _sig()
    key = (str(sig.subject), sig.attribution)
    committed = _lineages("the shared reading")
    in_flight = {key: [LineageView(hypothesis_id=None, key=key,
                                   current_stance=Stance.AFFIRMS, in_flight=True,
                                   in_flight_statement="the shared reading",
                                   in_flight_signature=sig)]}
    d = DeterministicAdjudicator().adjudicate(
        CandidateProposal("c1", "the shared reading", _view()), sig,
        committed=committed, in_flight=in_flight,
    )
    assert d.matched_in_flight is False
    assert d.matched_hypothesis_id == "hyp-1"


def test_build_committed_views_groups_lineages_sharing_a_bound():
    """M-2 at the projection boundary: grouping, not overwriting."""
    from sanuvia.application.reasoning.identity import build_committed_views

    key = ("p1", "sanuvia-working-reading")
    views = build_committed_views(
        lineage_keys={key: "hyp-1"},
        current_stance={"hyp-1": Stance.OPEN},
        histories={"hyp-1": (_version("a reading"),)},
    )
    assert isinstance(views[key], list)
    assert len(views[key]) == 1
