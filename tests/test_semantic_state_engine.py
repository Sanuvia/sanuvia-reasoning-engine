"""Slice 1 end to end, through the running engine.

Technical Design v1.5.4. These exercise ``ReasoningService.record_interaction``
-- the real path, not isolated components -- and assert the governed properties
hold where they actually matter: service -> core loop -> adjudication -> plan ->
validation -> ``commit_plan`` -> persistence.

The R1 model-assisted resolver is **not** configured here, because it remains
Slice 2. ``REFINE_EXISTING`` is therefore unreachable and asserted so.
"""

from __future__ import annotations

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import (
    Appraisal,
    AppraisalResponse,
    Bearing,
    BearingKind,
    CandidateProposal,
    CommitmentSignatureView,
    HypothesisHandle,
    ProposedHypothesis,
)
from sanuvia.application.reasoning import model_revision
from sanuvia.domain import (
    ClaimClass,
    EvidenceClass,
    EvidenceRecordId,
    GovernedOutcome,
    GovernedRejection,
    IdentityOutcome,
    Stance,
)

SUBJECT = "subject-1"


def _service(script=None, *, store=None, appraiser=None, ids=None, clock=None):
    store = store or InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=appraiser if appraiser is not None else ScriptedAppraiser(script or {}),
        ids=ids or SequentialIdGenerator(),
        clock=clock or ManualClock(),
    )
    return ReasoningService(deps), store, deps


def _ev(text: str) -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE, content=text,
        source="extractor:test", reliability=0.8, classification_confidence=0.9,
    )


def _proposes(evidence_id: str, statement: str, authored_id: str = "H1") -> dict:
    return {
        EvidenceRecordId(evidence_id): Appraisal(
            proposals=(ProposedHypothesis(authored_id, statement, 0.4, ()),)
        )
    }


# --- durable identity is engine-issued, after adjudication -------------------


def test_durable_id_is_engine_issued_not_model_authored():
    """Locked §3.3: the engine issues every durable hypothesis id.

    The fixture authors ``H1``; nothing named ``H1`` may reach the store.
    """
    svc, store, _ = _service(_proposes("evidence-1", "the working reading"))
    svc.record_interaction(SUBJECT, [_ev("first")])
    ids = {h.hypothesis_id for h in store.hypotheses.list_for_subject(SUBJECT)}
    assert ids == {"hyp-1"}
    assert "H1" not in ids


def test_no_durable_hypothesis_exists_before_adjudication_runs():
    """A rejected interaction leaves no lineage, no version, no hypothesis."""
    class _Unknown:
        def appraise(self, request):
            return AppraisalResponse(
                bearings=(Bearing(HypothesisHandle("never-issued"), BearingKind.SUPPORTS),)
            )

    svc, store, _ = _service(appraiser=_Unknown())
    with pytest.raises(GovernedRejection) as e:
        svc.record_interaction(SUBJECT, [_ev("first")])
    assert e.value.outcome is GovernedOutcome.UNKNOWN_HYPOTHESIS_REFERENCE
    assert store.hypotheses.list_for_subject(SUBJECT) == []
    assert store.lineages.list_for_subject(SUBJECT) == []


def test_r6_initial_support_comes_from_the_existing_mechanism():
    """R6: support_after_support(0.0, reliability, learning_rate).

    reliability 0.8 x learning_rate 0.5 = 0.4. No separate initial-support
    constant exists, and the model supplies no support value.
    """
    svc, store, _ = _service(_proposes("evidence-1", "the working reading"))
    svc.record_interaction(SUBJECT, [_ev("first")])
    (h,) = store.hypotheses.list_for_subject(SUBJECT)
    assert h.support.value == pytest.approx(0.4)


# --- evidence-first ordering is closed ---------------------------------------


def test_rejected_interaction_persists_no_evidence():
    """The headline defect. The old core loop wrote evidence BEFORE appraisal, so
    a failed appraisal left evidence persisted with no revision."""
    class _Unknown:
        def appraise(self, request):
            return AppraisalResponse(
                bearings=(Bearing(HypothesisHandle("never-issued"), BearingKind.SUPPORTS),)
            )

    svc, store, _ = _service(appraiser=_Unknown())
    with pytest.raises(GovernedRejection):
        svc.record_interaction(SUBJECT, [_ev("first")])
    assert store.evidence.list_for_subject(SUBJECT) == [], (
        "evidence must not survive a rejected plan"
    )


def test_appraiser_failure_persists_nothing():
    """An adapter that raises mid-interaction must leave state untouched."""
    class _Explodes:
        def appraise(self, request):
            raise RuntimeError("appraiser boom")

    svc, store, _ = _service(appraiser=_Explodes())
    with pytest.raises(RuntimeError):
        svc.record_interaction(SUBJECT, [_ev("first")])
    assert store.evidence.list_for_subject(SUBJECT) == []
    assert store.hypotheses.list_for_subject(SUBJECT) == []


def test_commit_plan_is_the_only_writer_in_the_engine_module():
    """§1.5 sole-writer invariant, asserted structurally over the source."""
    import inspect
    import re

    src = inspect.getsource(model_revision)
    start = src.index("def commit_plan")
    end = src.index("class ModelRevisionEngine")
    outside = src[:start] + src[end:]
    writes = [
        line.strip()
        for line in outside.splitlines()
        if re.search(r"\b(d|self\._d|deps)\.\w+\.(add|append|add_edge|append_version|set_current_pointer)\(", line)
    ]
    assert writes == [], f"store writes outside commit_plan: {writes}"


# --- atomic rollback ---------------------------------------------------------


def test_rejection_rolls_back_every_store_and_the_id_generator():
    """F-4 / F-6: stores AND counters, on a pre-mutation rejection."""
    class _Unknown:
        def appraise(self, request):
            return AppraisalResponse(
                bearings=(Bearing(HypothesisHandle("never-issued"), BearingKind.SUPPORTS),)
            )

    ids = SequentialIdGenerator()
    svc, store, _ = _service(appraiser=_Unknown(), ids=ids)
    with pytest.raises(GovernedRejection):
        svc.record_interaction(SUBJECT, [_ev("first")])
    # Every bundle store is empty, and the counters are back where they started.
    assert store.evidence.list_for_subject(SUBJECT) == []
    assert store.ledger.read(SUBJECT) == []
    assert store.lineages.list_for_subject(SUBJECT) == []
    assert ids.new_id("evidence") == "evidence-1"


def test_successful_interaction_advances_ids_normally():
    """Rollback must not leak into the committed path."""
    ids = SequentialIdGenerator()
    svc, store, _ = _service(_proposes("evidence-1", "a reading"), ids=ids)
    svc.record_interaction(SUBJECT, [_ev("first")])
    assert store.evidence.list_for_subject(SUBJECT) != []
    assert ids.new_id("evidence") == "evidence-2"


# --- deterministic identity through the running engine -----------------------


def _two_interactions(statement_a: str, statement_b: str, authored_b: str = "H1"):
    store = InMemoryReasoningStore()
    ids, clock = SequentialIdGenerator(), ManualClock()
    script = _proposes("evidence-1", statement_a, "H1")
    svc, _, _ = _service(script, store=store, ids=ids, clock=clock)
    svc.record_interaction(SUBJECT, [_ev("first")])
    script2 = _proposes("evidence-2", statement_b, authored_b)
    svc2, _, _ = _service(script2, store=store, ids=ids, clock=clock)
    svc2.record_interaction(SUBJECT, [_ev("second")])
    return store


def test_exact_duplicate_across_interactions_creates_no_second_lineage():
    """MATCH_EXISTING against committed state. This is the Run 002 pattern."""
    store = _two_interactions("the working reading", "the working reading")
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    (h,) = store.hypotheses.list_for_subject(SUBJECT)
    assert h.supporting_evidence_ids == ("evidence-1", "evidence-2")


def test_distinct_statement_under_a_new_lineage_key_creates_a_second_lineage():
    """Locked §3.4 plurality: genuinely distinct readings stay distinct."""
    store = _two_interactions("the first reading", "a different reading", "H2")
    assert len(store.lineages.list_for_subject(SUBJECT)) == 2


def test_statement_history_is_recorded_and_matched():
    """F-2: a re-presented statement identifies its lineage via history."""
    store = _two_interactions("the working reading", "the working reading")
    history = store.statement_versions.history("hyp-1")
    assert [v.statement for v in history] == ["the working reading"]
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1


def test_in_flight_duplicate_within_one_interaction_creates_one_lineage():
    """Two records in ONE interaction proposing the same commitment.

    Nothing is committed when the second is adjudicated, so only the in-flight
    arm can catch it -- the exact case a committed-state-only rule misses.
    """
    script = {
        EvidenceRecordId("evidence-1"): Appraisal(
            proposals=(ProposedHypothesis("H1", "the same reading", 0.4, ()),)),
        EvidenceRecordId("evidence-2"): Appraisal(
            proposals=(ProposedHypothesis("H1", "the same reading", 0.4, ()),)),
    }
    svc, store, _ = _service(script)
    svc.record_interaction(SUBJECT, [_ev("first"), _ev("second")])
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1


def test_unresolved_plausible_candidate_parks_while_r1_is_unconfigured():
    """§2 G: plausible-but-inexact parks rather than committing on an unmade
    judgement. The proposal is preserved, not discarded."""
    store = _two_interactions("the working reading", "a paraphrase of that reading")
    parked = store.identity_adjudications.list_for_subject(SUBJECT)
    assert len(parked) == 1
    record = parked[0]
    assert record.decision.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    assert record.candidate_statement == "a paraphrase of that reading"
    assert record.source_evidence_ids == ("evidence-2",)
    # Parked, so it created no hypothesis and no second lineage.
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1


def test_parked_candidate_creates_no_hypothesis_and_survives_a_hold():
    """Ruling Q2: parked candidates are created, preserved and reported; they
    are not re-adjudicated by a hold."""
    store = _two_interactions("the working reading", "a paraphrase of that reading")
    before = len(store.identity_adjudications.list_for_subject(SUBJECT))
    ids, clock = SequentialIdGenerator(), ManualClock()
    svc, _, _ = _service({}, store=store, ids=ids, clock=clock)
    svc.record_interaction(SUBJECT, [])  # no-evidence hold
    after = store.identity_adjudications.list_for_subject(SUBJECT)
    assert len(after) == before
    assert after[0].status.value == "PARKED"


def test_refine_existing_is_unreachable_through_the_running_engine():
    """R1 remains Slice 2, so no engine path can produce REFINE_EXISTING."""
    store = _two_interactions("the working reading", "a paraphrase of that reading")
    outcomes = {
        r.decision.outcome
        for r in store.identity_adjudications.list_for_subject(SUBJECT)
    }
    assert IdentityOutcome.REFINE_EXISTING not in outcomes
    assert store.statement_versions.history("hyp-1") == [
        store.statement_versions.current("hyp-1")
    ], "no refinement appended a second version"


# --- hold semantics ----------------------------------------------------------


def test_no_evidence_hold_changes_nothing_and_is_not_a_rejection():
    """§3.6 / locked §3.9: the hold writes nothing and is not REJECTED_PLAN."""
    svc, store, _ = _service(_proposes("evidence-1", "a reading"))
    svc.record_interaction(SUBJECT, [_ev("first")])
    before = (
        len(store.evidence.list_for_subject(SUBJECT)),
        len(store.hypotheses.list_for_subject(SUBJECT)),
        len(store.ledger.read(SUBJECT)),
        len(store.lineages.list_for_subject(SUBJECT)),
    )
    result = svc.record_interaction(SUBJECT, [])  # hold -- no exception
    after = (
        len(store.evidence.list_for_subject(SUBJECT)),
        len(store.hypotheses.list_for_subject(SUBJECT)),
        len(store.ledger.read(SUBJECT)),
        len(store.lineages.list_for_subject(SUBJECT)),
    )
    assert before == after
    assert result.committed is False
    assert result.ingested_evidence == ()


def test_hold_does_not_consume_identifiers():
    """The hold terminates before canonical identity is minted."""
    ids = SequentialIdGenerator()
    svc, _, _ = _service({}, ids=ids)
    svc.record_interaction(SUBJECT, [])
    assert ids.new_id("evidence") == "evidence-1"


# --- governed outcomes on the integrated path --------------------------------


def test_non_appraisable_record_never_reaches_the_appraiser():
    """Ruling Q1, structurally: no appraisal call is made at all."""
    from sanuvia.domain import (
        EvidenceRole, EvidenceSourceKind, EvidenceStanding, EvidenceSubjectKind,
    )

    calls: list = []

    class _Counting:
        def appraise(self, request):
            calls.append(request.observation_id)
            return AppraisalResponse()

    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(store=store, appraiser=_Counting())
    svc = ReasoningService(deps)
    standing = EvidenceStanding(
        source_kind=EvidenceSourceKind.PARTICIPANT,
        subject_kind=EvidenceSubjectKind.NONE,
        role=EvidenceRole.RESPONSE_OR_RESONANCE, source_id="pA",
    )
    svc.record_interaction(
        SUBJECT,
        [EvidenceInput(subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE,
                       content="that lands", source="t", reliability=0.8,
                       classification_confidence=0.9, standing=standing)],
    )
    assert calls == [], "a resonance record must receive no appraisal call"
    # Admitted and preserved, with its standing.
    (rec,) = store.evidence.list_for_subject(SUBJECT)
    assert rec.standing is not None and rec.standing.role is EvidenceRole.RESPONSE_OR_RESONANCE


def test_statement_capture_failure_rejects_before_identity():
    """An empty statement is a governed failure, not something to repair."""
    class _Empty:
        def appraise(self, request):
            label = request.participants[0]
            return AppraisalResponse(
                proposals=(CandidateProposal("c1", "", CommitmentSignatureView(
                    subject=label, attribution="a", claim_class=ClaimClass.INTERPRETATION,
                    stance=Stance.OPEN)),)
            )

    svc, store, _ = _service(appraiser=_Empty())
    with pytest.raises(GovernedRejection) as e:
        svc.record_interaction(SUBJECT, [_ev("first")])
    assert e.value.outcome is GovernedOutcome.STATEMENT_CAPTURE_FAILURE
    assert store.evidence.list_for_subject(SUBJECT) == []


def test_duplicate_proposals_in_one_response_reject_the_interaction():
    script = {
        EvidenceRecordId("evidence-1"): Appraisal(
            proposals=(
                ProposedHypothesis("H1", "the same reading", 0.4, ()),
                ProposedHypothesis("H1", "the same reading", 0.4, ()),
            )
        )
    }
    svc, store, _ = _service(script)
    with pytest.raises(GovernedRejection) as e:
        svc.record_interaction(SUBJECT, [_ev("first")])
    assert e.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert store.evidence.list_for_subject(SUBJECT) == []


def test_evidence_attaches_to_the_matched_lineage():
    """Evidence attachment semantics through the running engine."""
    store = _two_interactions("the working reading", "the working reading")
    (h,) = store.hypotheses.list_for_subject(SUBJECT)
    assert set(h.supporting_evidence_ids) == {"evidence-1", "evidence-2"}
    assert h.support.value > 0.4, "the second observation strengthened the lineage"
