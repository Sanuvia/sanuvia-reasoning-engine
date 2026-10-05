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
from sanuvia.application.reasoning.unit_of_work import bundle_stores
from sanuvia.domain import (
    VOICE_SANUVIA_WORKING_READING,
    BreachKind,
    ClaimClass,
    EvidenceClass,
    EvidenceRecordId,
    GovernedOutcome,
    GovernedRejection,
    IdentityOutcome,
    Stance,
)

SUBJECT = "subject-1"


def _service(script=None, *, store=None, appraiser=None, ids=None, clock=None,
             resolver=None):
    """Build a service. ``resolver`` defaults to None -- the real deterministic
    arm, with no R1 -- so a test must opt in to the fixture-authored double."""
    store = store or InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=appraiser if appraiser is not None else ScriptedAppraiser(script or {}),
        ids=ids or SequentialIdGenerator(),
        clock=clock or ManualClock(),
        identity_resolver=resolver,
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


def _two_interactions(statement_a: str, statement_b: str, authored_b: str = "H1",
                      *, resolver=None):
    """Two interactions over one store. ``resolver`` is None unless a test is
    exercising the fixture-authored double."""
    store = InMemoryReasoningStore()
    ids, clock = SequentialIdGenerator(), ManualClock()
    script = _proposes("evidence-1", statement_a, "H1")
    svc, _, _ = _service(script, store=store, ids=ids, clock=clock, resolver=resolver)
    svc.record_interaction(SUBJECT, [_ev("first")])
    script2 = _proposes("evidence-2", statement_b, authored_b)
    svc2, _, _ = _service(script2, store=store, ids=ids, clock=clock, resolver=resolver)
    svc2.record_interaction(SUBJECT, [_ev("second")])
    return store


def test_exact_duplicate_across_interactions_creates_no_second_lineage():
    """MATCH_EXISTING against committed state. This is the Run 002 pattern."""
    store = _two_interactions("the working reading", "the working reading")
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    (h,) = store.hypotheses.list_for_subject(SUBJECT)
    assert h.supporting_evidence_ids == ("evidence-1", "evidence-2")


def test_distinct_statement_parks_when_no_resolver_is_configured():
    """§2 G Reading A: a non-exact candidate under a populated bound parks.

    ``attribution`` is a voice label (§2 H), so a second distinct reading for
    the same subject shares the retrieval bound rather than founding its own.
    It is therefore a *plausible* candidate at resolution-order case 4, and
    with no resolver configured the stated unconfigured behaviour is to park
    rather than commit on an unmade judgement.

    This is the real deterministic-arm behaviour and the real External-path
    behaviour until R1 lands. It must NOT default to DISTINCT_NEW: doing so
    would discharge the §3.4 burden-of-distinctness by assumption, declaring
    every non-exact statement distinct without any comparison -- the Run 002
    duplication mechanism.
    """
    store = _two_interactions("the first reading", "a different reading", "H2")
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1, "no second lineage"

    (parked,) = store.identity_adjudications.list_for_subject(SUBJECT)
    assert parked.decision.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    assert parked.candidate_statement == "a different reading"
    # Parked, not discarded: the candidate and its plausible matches survive.
    assert parked.plausible_matches


def test_distinct_lineages_coexist_when_the_resolver_authors_distinct_new():
    """§3.4 plurality, via an explicitly authored identity decision.

    Several lineages CAN share one retrieval bound -- which is what M-2's
    plural structures exist for -- but only once something with the authority
    to decide says so. Here that is the fixture-authored test double returning
    the decision the fixture stated. It compares nothing.
    """
    from sanuvia.adapters.reasoning.scripted_identity_resolver import (
        ScriptedIdentityResolver,
    )

    resolver = ScriptedIdentityResolver(["H1", "H2"])
    store = _two_interactions("the first reading", "a different reading", "H2",
                              resolver=resolver)

    lineages = store.lineages.list_for_subject(SUBJECT)
    assert len(lineages) == 2, "two distinct commitments coexist"
    # Both under the SAME governed retrieval bound -- that is the point.
    assert len({l.lineage_key for l in lineages}) == 1
    assert {l.attribution for l in lineages} == {VOICE_SANUVIA_WORKING_READING}
    assert len(store.hypotheses.list_for_subject(SUBJECT)) == 2
    # Nothing parked: the decision was authored, not deferred.
    assert store.identity_adjudications.list_for_subject(SUBJECT) == []
    # And it was recorded as fixture-authored.
    assert [d.outcome for d in resolver.decisions_made] == [
        IdentityOutcome.DISTINCT_NEW
    ]


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


# --- M-6: the governed request identifier comes from the injected generator ---


def _request_ids_seen(appraiser_box: list) -> list[str]:
    return [r.request_id for r in appraiser_box]


class _RecordsRequests:
    """Appraiser that records the request id it was handed, then proposes."""

    def __init__(self, statement: str = "a reading", authored_id: str = "H1") -> None:
        self.seen: list = []
        self._inner = ScriptedAppraiser({})
        self._statement, self._authored = statement, authored_id

    def appraise(self, request):
        self.seen.append(request)
        self._inner.set(
            request.observation_id,
            Appraisal(proposals=(ProposedHypothesis(self._authored, self._statement, 0.4, ()),)),
        )
        return self._inner.appraise(request)


def test_request_id_is_allocated_through_the_injected_generator():
    """M-6: no ad-hoc uuid or process-local identifier on the governed path.

    The request id appears in every handle and in the text of every governed
    rejection, so an ad-hoc source makes two otherwise identical runs differ.
    """
    appraiser = _RecordsRequests()
    ids = SequentialIdGenerator()
    svc, _, _ = _service(appraiser=appraiser, ids=ids)
    svc.record_interaction(SUBJECT, [_ev("first")])

    assert len(appraiser.seen) == 1
    request_id = appraiser.seen[0].request_id
    # Allocated by the generator under the "req" kind, not uuid4.
    assert request_id == "req-1"
    # The generator's own counter advanced, which is what makes it restorable.
    assert ids.new_id("req") == "req-2"


def test_request_ids_are_reproducible_across_identical_runs():
    """M-6: an identical run must allocate identical request ids."""
    def run() -> list[str]:
        appraiser = _RecordsRequests()
        svc, _, _ = _service(appraiser=appraiser, ids=SequentialIdGenerator(),
                             clock=ManualClock())
        svc.record_interaction(SUBJECT, [_ev("first")])
        svc.record_interaction(SUBJECT, [_ev("second")])
        return _request_ids_seen(appraiser.seen)

    first, second = run(), run()
    assert first == second == ["req-1", "req-2"]


def test_rejected_interaction_does_not_consume_a_request_identifier():
    """M-6 + F-4/F-6: request-id allocation participates in snapshot/restore.

    A rejected plan must not permanently consume an identifier. Because the
    request id is now allocated through the generator the UnitOfWork restores,
    the next interaction allocates the SAME id the rejected one did -- which is
    the property that makes a rerun after a rejection byte-reproducible.
    """
    class _UnknownThenPropose:
        """Rejects the first interaction, proposes normally on the second."""

        def __init__(self) -> None:
            self.seen: list = []
            self._calls = 0
            self._inner = ScriptedAppraiser({})

        def appraise(self, request):
            self.seen.append(request)
            self._calls += 1
            if self._calls == 1:
                return AppraisalResponse(
                    bearings=(Bearing(HypothesisHandle("never-issued"),
                                      BearingKind.SUPPORTS),)
                )
            self._inner.set(
                request.observation_id,
                Appraisal(proposals=(ProposedHypothesis("H1", "a reading", 0.4, ()),)),
            )
            return self._inner.appraise(request)

    appraiser = _UnknownThenPropose()
    ids = SequentialIdGenerator()
    svc, store, _ = _service(appraiser=appraiser, ids=ids)

    with pytest.raises(GovernedRejection):
        svc.record_interaction(SUBJECT, [_ev("first")])
    assert store.evidence.list_for_subject(SUBJECT) == []

    svc.record_interaction(SUBJECT, [_ev("second")])
    # The rejected interaction's request id was returned to the pool.
    assert _request_ids_seen(appraiser.seen) == ["req-1", "req-1"]
    assert store.evidence.list_for_subject(SUBJECT) != []


# --- M-3: a refused commit leaves no orphan durable reasoning state ----------


class _CreatesThenReferencesUnknown:
    """Founds a lineage, then forces a governed rejection in the same response."""

    def appraise(self, request):
        return AppraisalResponse(
            proposals=(
                CandidateProposal(
                    "c1", "a provisional reading",
                    CommitmentSignatureView(
                        subject="p1", attribution="voice",
                        claim_class=ClaimClass.INTERPRETATION, stance=Stance.OPEN,
                    ),
                ),
            ),
            bearings=(Bearing(HypothesisHandle("never-issued"), BearingKind.SUPPORTS),),
        )


def test_rejection_after_provisional_creation_leaves_no_orphan_state():
    """M-3: provisional lineage/version state must not survive a refusal.

    The candidate founds a lineage during planning; an unknown hypothesis
    handle in the same response then rejects the interaction. Nothing may
    persist -- not the lineage, not its statement version, not the hypothesis.
    """
    svc, store, _ = _service(appraiser=_CreatesThenReferencesUnknown())
    with pytest.raises(GovernedRejection) as exc:
        svc.record_interaction(SUBJECT, [_ev("first")])
    assert exc.value.outcome is GovernedOutcome.UNKNOWN_HYPOTHESIS_REFERENCE

    assert store.lineages.list_for_subject(SUBJECT) == []
    assert list(store.statement_versions.history("hyp-1")) == []
    assert store.hypotheses.list_for_subject(SUBJECT) == []
    assert store.evidence.list_for_subject(SUBJECT) == []
    assert store.ledger.read(SUBJECT) == []


class _DeclinesHypothesize:
    """Commit policy that refuses to commit a HYPOTHESIZE event.

    The shipped PlaceholderCommitAllPolicy commits everything, so this
    condition is latent rather than currently reachable. The RevisionCommitPolicy
    port exists precisely so a real policy can be injected (FR-MR-003), and a
    policy that declines a hypothesize is the case that exposes the orphan.
    """

    def should_commit(self, event) -> bool:
        return event.outcome.value != "hypothesize"


def test_hold_after_provisional_creation_persists_no_lineage_or_version():
    """M-3: a held interaction must not write state for uncommitted hypotheses.

    When the commit policy declines the revision event, the interaction holds:
    no hypothesis record, no ledger entry, no WorldModel version. The lineage
    and statement version created provisionally during adjudication belong to a
    hypothesis the model does not hold, so persisting them would leave a
    StatementVersion whose created_at_version names a WorldModel version that
    was never appended.
    """
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=ScriptedAppraiser(_proposes("evidence-1", "a reading")),
        ids=SequentialIdGenerator(),
        clock=ManualClock(),
    )
    object.__setattr__(deps, "commit_policy", _DeclinesHypothesize())
    result = ReasoningService(deps).record_interaction(SUBJECT, [_ev("first")])

    # The interaction held: nothing committed.
    assert result.committed is False
    assert store.hypotheses.list_for_subject(SUBJECT) == []
    assert store.ledger.read(SUBJECT) == []

    # ... and therefore no orphan reasoning state for the uncommitted lineage.
    assert store.lineages.list_for_subject(SUBJECT) == []
    assert list(store.statement_versions.history("hyp-1")) == []


def test_held_interaction_still_preserves_its_audit_record():
    """M-3 / TD-18: rejected reasoning state and interaction audit differ.

    The same hold that writes no lineage must still record that the
    interaction happened. Audit preservation is governed and survives; the
    uncommitted reasoning state does not.
    """
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=ScriptedAppraiser(_proposes("evidence-1", "a reading")),
        ids=SequentialIdGenerator(),
        clock=ManualClock(),
    )
    object.__setattr__(deps, "commit_policy", _DeclinesHypothesize())
    ReasoningService(deps).record_interaction(SUBJECT, [_ev("first")])

    # The evidence that drove the held interaction is preserved as audit.
    assert len(store.evidence.list_for_subject(SUBJECT)) == 1
    # But no reasoning state was committed for it.
    assert store.lineages.list_for_subject(SUBJECT) == []
    assert store.hypotheses.list_for_subject(SUBJECT) == []


# --- M-5: unavailable rollback is a visible governed condition ---------------


def test_rollback_capability_is_reported_not_inferred():
    """M-5: the service answers directly whether a rollback boundary exists."""
    svc, _, _ = _service(_proposes("evidence-1", "a reading"))
    available, reason = svc.rollback_capability()
    assert available is True
    assert "snapshotable" in reason


def test_semantic_state_path_without_rollback_is_a_governed_failure():
    """M-5: the mutation path must not run silently without the boundary.

    A bundle carrying the Phase 1 semantic-state stores is on the governed
    path, so a missing rollback boundary is a commit-atomicity breach rather
    than a configuration detail. Previously this returned None and the whole
    mutation path ran with nothing to undo it.
    """
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=ScriptedAppraiser(_proposes("evidence-1", "a reading")),
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )

    # Remove snapshot support from one store in the bundle.
    class _NoSnapshot:
        def __getattr__(self, name):
            if name == "snapshot":
                raise AttributeError(name)
            return getattr(store.evidence, name)

    object.__setattr__(store, "evidence", _NoSnapshot())
    svc = ReasoningService(deps)

    available, reason = svc.rollback_capability()
    assert available is False
    assert "evidence" in reason

    with pytest.raises(GovernedRejection) as exc:
        svc.record_interaction(SUBJECT, [_ev("first")])
    assert exc.value.outcome is GovernedOutcome.NON_ATOMIC_REVISION_PLAN
    assert exc.value.breach_kind is BreachKind.COMMIT_ATOMICITY
    # The mutation path did not run.
    assert store.hypotheses.list_for_subject(SUBJECT) == []


def test_documented_sqlite_scope_exclusion_is_preserved():
    """M-5: §5.9 keeps SQLite outside the Phase 1 path -- it still runs.

    The governed condition must not become a blanket requirement that breaks
    an adapter the design explicitly excludes. A bundle carrying none of the
    semantic-state stores proceeds without the boundary, as before.
    """
    from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
    from sanuvia.adapters.wiring import build_sqlite_dependencies

    sqlite_store = SqliteReasoningStore(":memory:")
    deps = build_sqlite_dependencies(
        store=sqlite_store,
        appraiser=ScriptedAppraiser(_proposes("evidence-1", "a reading")),
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    svc = ReasoningService(deps)

    # It carries no semantic-state stores, so it is outside the governed path.
    assert deps.lineages is None
    # And it records an interaction without raising.
    result = svc.record_interaction(SUBJECT, [_ev("first")])
    assert result is not None
    assert sqlite_store.evidence.list_for_subject(SUBJECT) != []


# --- M-4 / TD-03: source-reference mapping on the RUNNING engine -------------


def _ev_ref(text: str, ref) -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE, content=text,
        source="extractor:test", reliability=0.8, classification_confidence=0.9,
        source_ref=ref,
    )


def test_td03_round_trip_resolves_in_both_directions_through_the_engine():
    """TD-03: evidence-N <-> (transcript, interaction, k), both ways.

    Driven through ``record_interaction`` rather than an index the test builds
    itself, which is the distinction M-4 draws: the mapping is validated on the
    running engine, not merely in principle.
    """
    from sanuvia.domain import SourceObservationRef

    refs = [SourceObservationRef("case-001", 3, k) for k in range(3)]
    svc, store, _ = _service(appraiser=ScriptedAppraiser({}))
    svc.record_interaction(SUBJECT, [_ev_ref(f"observation {k}", r)
                                     for k, r in enumerate(refs)])

    records = store.evidence.list_for_subject(SUBJECT)
    assert len(records) == 3

    for record in records:
        # forward: source observation -> canonical evidence id
        assert store.evidence.id_for_ref(record.source_ref) == record.id
        # reverse: canonical evidence id -> source observation
        assert store.evidence.ref_for_id(record.id) == record.source_ref


def test_td03_within_interaction_index_keeps_observations_distinct():
    """TD-03: k distinct.

    §2 A records the gap this closes: without the within-interaction index,
    one interaction's three observations were indistinguishable.
    """
    from sanuvia.domain import SourceObservationRef

    refs = [SourceObservationRef("case-001", 3, k) for k in range(3)]
    svc, store, _ = _service(appraiser=ScriptedAppraiser({}))
    svc.record_interaction(SUBJECT, [_ev_ref(f"observation {k}", r)
                                     for k, r in enumerate(refs)])

    mapped = {store.evidence.id_for_ref(r) for r in refs}
    assert len(mapped) == 3, "three observations must map to three distinct ids"
    assert {store.evidence.ref_for_id(m).observation_index for m in mapped} == {0, 1, 2}


def test_td03_conflicting_source_mapping_is_a_governed_failure_on_the_engine():
    """TD-03 / check 7: a ref that already maps elsewhere rejects the plan.

    The second interaction re-presents interaction 3's k=0 observation under a
    new canonical id. Because the index is now supplied from the store, the
    running engine detects the conflict; previously check 7 received an empty
    mapping and could not fire however the engine behaved.
    """
    from sanuvia.domain import SourceObservationRef

    ref = SourceObservationRef("case-001", 3, 0)
    svc, store, _ = _service(appraiser=ScriptedAppraiser({}))
    svc.record_interaction(SUBJECT, [_ev_ref("first admission", ref)])

    with pytest.raises(GovernedRejection) as exc:
        svc.record_interaction(SUBJECT, [_ev_ref("second admission", ref)])
    assert exc.value.outcome is GovernedOutcome.SOURCE_REFERENCE_MAPPING_FAILURE

    # Rejected: the second admission wrote nothing.
    assert len(store.evidence.list_for_subject(SUBJECT)) == 1


def test_source_ref_index_is_restored_on_rejection():
    """M-4 + F-9: the ref index is a mutable container the store owns.

    If a rejected plan left it populated, check 7 would reject the retry of an
    interaction that never committed.
    """
    from sanuvia.domain import SourceObservationRef

    ref = SourceObservationRef("case-001", 1, 0)

    class _Unknown:
        def appraise(self, request):
            return AppraisalResponse(
                bearings=(Bearing(HypothesisHandle("never-issued"),
                                  BearingKind.SUPPORTS),)
            )

    svc, store, _ = _service(appraiser=_Unknown())
    with pytest.raises(GovernedRejection):
        svc.record_interaction(SUBJECT, [_ev_ref("first", ref)])

    assert store.evidence.source_ref_index() == {}, "index must roll back too"
    # The same ref is therefore admissible afterwards.
    svc2, store2, _ = _service(appraiser=ScriptedAppraiser({}))
    svc2.record_interaction(SUBJECT, [_ev_ref("retry", ref)])
    assert store2.evidence.id_for_ref(ref) is not None


# --- 1.3: HypothesisView signatures come from stored state ------------------


class _CapturesRequests:
    """Records each AppraisalRequest, proposing once so a lineage exists."""

    def __init__(self, statement: str = "a reading") -> None:
        self.seen: list = []
        self._inner = ScriptedAppraiser({})
        self._statement = statement
        self._proposed = False

    def appraise(self, request):
        self.seen.append(request)
        if self._proposed:
            return AppraisalResponse()
        self._proposed = True
        self._inner.set(
            request.observation_id,
            Appraisal(proposals=(ProposedHypothesis("H1", self._statement, 0.4, ()),)),
        )
        return self._inner.appraise(request)


def test_hypothesis_view_signature_uses_the_stored_lineage_values():
    """M-1.3: subject and attribution are read from the lineage, not rebuilt.

    The stored values are whose commitment the lineage records. Substituting
    the request's participant label would silently re-attribute a commitment
    whenever a later request concerns a different participant -- the
    cross-attribution merge §2 H's immutable pair exists to prevent.
    """
    appraiser = _CapturesRequests()
    svc, store, _ = _service(appraiser=appraiser)
    svc.record_interaction(SUBJECT, [_ev("first")])
    svc.record_interaction(SUBJECT, [_ev("second")])

    (lineage,) = store.lineages.list_for_subject(SUBJECT)
    # The second request offers the committed hypothesis back to the appraiser.
    request = appraiser.seen[1]
    offered = request.existing
    assert len(offered) == 1
    signature = offered[0].signature

    # Attribution is the stored, immutable value.
    assert signature.attribution == lineage.attribution

    # The SUBJECT is a request-scoped participant LABEL, not the stored
    # ParticipantId. The stored value identifies whose commitment the lineage
    # records; the label is how that participant is named inside this request.
    # Asserting equality with the stored id would assert the leak.
    assert signature.subject in request.participants
    assert signature.subject != lineage.signature_subject


def test_hypothesis_view_signature_uses_current_statement_version_fields():
    """M-1.3: claim_class/stance/temporal_scope are versioned, not hardcoded.

    They were pinned to INTERPRETATION/OPEN, so the view disagreed with stored
    state for any lineage whose current version differed.
    """
    appraiser = _CapturesRequests()
    svc, store, _ = _service(appraiser=appraiser)
    svc.record_interaction(SUBJECT, [_ev("first")])

    (lineage,) = store.lineages.list_for_subject(SUBJECT)
    (version,) = list(store.statement_versions.history(lineage.hypothesis_id))

    svc.record_interaction(SUBJECT, [_ev("second")])
    signature = appraiser.seen[1].existing[0].signature
    assert signature.claim_class is version.claim_class
    assert signature.stance is version.stance
    assert signature.temporal_scope == version.temporal_scope


def test_hypothesis_view_signature_never_carries_a_durable_identifier():
    """M-1.3: identity is not reconstructed into the attribution.

    The lineage-less fallback previously used the durable hypothesis id as the
    attribution, which made identity look like a voice label.
    """
    appraiser = _CapturesRequests()
    svc, store, _ = _service(appraiser=appraiser)
    svc.record_interaction(SUBJECT, [_ev("first")])
    svc.record_interaction(SUBJECT, [_ev("second")])

    (lineage,) = store.lineages.list_for_subject(SUBJECT)
    request = appraiser.seen[1]
    signature = request.existing[0].signature

    # No durable hypothesis id.
    assert str(lineage.hypothesis_id) not in signature.attribution
    assert str(lineage.hypothesis_id) not in signature.subject

    # And no durable ParticipantId. TD-V1: nothing in a model-facing view may
    # carry a canonical EvidenceRecordId, a durable HypothesisId or a
    # ParticipantId. The subject previously leaked exactly this, because the
    # label lookup was performed in the wrong direction and always missed.
    assert signature.subject != str(lineage.signature_subject)
    assert signature.subject in request.participants, (
        "subject must be a request-scoped participant label"
    )


def test_hypothesis_view_subject_is_a_label_even_when_absent_from_the_observation():
    """TD-V1: a lineage subject outside this observation is still projected.

    A lineage founded under one participant can be offered back during a
    request whose observation concerns someone else. The subject must still
    render as a request-scoped label, which means it has to be added to the
    request's participant set rather than falling through to the durable id.
    """
    from sanuvia.domain import EvidenceStanding, EvidenceRole, EvidenceSourceKind
    from sanuvia.domain import EvidenceSubjectKind

    def ev(text: str, source: str, subject: str) -> EvidenceInput:
        return EvidenceInput(
            subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE,
            content=text, source="extractor:test", reliability=0.8,
            classification_confidence=0.9,
            standing=EvidenceStanding(
                source_kind=EvidenceSourceKind.PARTICIPANT,
                subject_kind=EvidenceSubjectKind.PARTICIPANT,
                role=EvidenceRole.ACCOUNT, source_id=source, subject_id=subject,
            ),
        )

    appraiser = _CapturesRequests()
    svc, store, _ = _service(appraiser=appraiser)
    svc.record_interaction(SUBJECT, [ev("first", source="pA", subject="pB")])
    # A later interaction about entirely different participants.
    svc.record_interaction(SUBJECT, [ev("second", source="pC", subject="pD")])

    (lineage,) = store.lineages.list_for_subject(SUBJECT)
    request = appraiser.seen[1]
    signature = request.existing[0].signature

    assert signature.subject in request.participants
    assert signature.subject != str(lineage.signature_subject)


def test_lineage_less_bundle_presents_a_constant_attribution():
    """M-1.3: the legacy path gets a constant, which cannot encode identity."""
    from sanuvia.application.reasoning.model_revision import UNGOVERNED_ATTRIBUTION
    from sanuvia.adapters.persistence.sqlite_store import SqliteReasoningStore
    from sanuvia.adapters.wiring import build_sqlite_dependencies

    appraiser = _CapturesRequests()
    deps = build_sqlite_dependencies(
        store=SqliteReasoningStore(":memory:"), appraiser=appraiser,
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    svc = ReasoningService(deps)
    svc.record_interaction(SUBJECT, [_ev("first")])
    svc.record_interaction(SUBJECT, [_ev("second")])

    offered = appraiser.seen[1].existing
    assert len(offered) == 1, "the legacy path still offers its hypotheses"
    assert offered[0].signature.attribution == UNGOVERNED_ATTRIBUTION


# --- M-7: transaction and sole-writer integrity -----------------------------


def test_td18_rejected_interaction_audit_is_distinct_from_rejected_state():
    """TD-18: a rejected interaction is recorded; its reasoning state is not.

    These are different boundaries. The interaction's rejection is audit and
    is reported to the caller; the reasoning-state mutation it attempted is
    rolled back in full. Asserting only one of the two would let either
    collapse into the other.
    """
    svc, store, _ = _service(appraiser=_CreatesThenReferencesUnknown())
    with pytest.raises(GovernedRejection) as exc:
        svc.record_interaction(SUBJECT, [_ev("first")])

    # Audit: the rejection is a governed, identified outcome, not an opaque error.
    assert exc.value.outcome is GovernedOutcome.UNKNOWN_HYPOTHESIS_REFERENCE
    assert exc.value.references

    # Reasoning state: nothing survived, across every store in the bundle.
    for name, s in bundle_stores(store).items():
        lister = getattr(s, "list_for_subject", None)
        if lister is not None:
            assert list(lister(SUBJECT)) == [], f"{name} retained rejected state"

def test_mid_commit_failure_rolls_back_atomically():
    """M-7: a failure part-way through commit_plan leaves nothing behind.

    Evidence is written first inside commit_plan, so failing a later write is
    the case that would otherwise leave evidence persisted with no revision --
    the evidence-first partial mutation the sole-writer boundary exists to
    close. The failure is injected after evidence has already been added.
    """
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=ScriptedAppraiser(_proposes("evidence-1", "a reading")),
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )

    real_add = store.hypotheses.add
    calls = {"n": 0}

    def exploding_add(record):
        calls["n"] += 1
        raise RuntimeError("injected mid-commit failure")

    object.__setattr__(store.hypotheses, "add", exploding_add)
    with pytest.raises(RuntimeError, match="injected mid-commit failure"):
        ReasoningService(deps).record_interaction(SUBJECT, [_ev("first")])
    object.__setattr__(store.hypotheses, "add", real_add)

    assert calls["n"] == 1, "the failure must have been reached mid-commit"
    # Evidence was written BEFORE the failing write, and must not survive it.
    assert store.evidence.list_for_subject(SUBJECT) == []
    assert store.lineages.list_for_subject(SUBJECT) == []
    assert store.ledger.read(SUBJECT) == []
    assert store.world_models.get_current_model(SUBJECT) is None


def test_mid_commit_failure_restores_identifier_counters():
    """M-7 + F-6: counters are part of the same boundary as the stores."""
    store = InMemoryReasoningStore()
    ids = SequentialIdGenerator()
    deps = build_in_memory_dependencies(
        store=store,
        appraiser=ScriptedAppraiser(_proposes("evidence-1", "a reading")),
        ids=ids, clock=ManualClock(),
    )
    real_add = store.hypotheses.add
    object.__setattr__(store.hypotheses, "add",
                       lambda r: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        ReasoningService(deps).record_interaction(SUBJECT, [_ev("first")])
    object.__setattr__(store.hypotheses, "add", real_add)

    assert ids.new_id("evidence") == "evidence-1"
    assert ids.new_id("req") == "req-1"
