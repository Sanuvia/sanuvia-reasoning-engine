"""R1 — the bounded model-assisted identity resolver (§2 G case 4).

The resolver is an adjudicator WITHIN the R1 interface, never the owner of
durable identity. These exercise the boundary: what reaches it, what it may
return, what the application does with the answer, and what it may never do.

Fake clients only. No provider is selected, nothing reaches a network, and no
model inference is run.
"""

from __future__ import annotations

from typing import Any

import json

import pytest

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.support.deterministic import ManualClock, SequentialIdGenerator
from sanuvia.adapters.wiring import build_in_memory_dependencies
from sanuvia.application.api.service import EvidenceInput, ReasoningService
from sanuvia.application.ports.reasoning import (
    AppraisalRequest,
    AppraisalResponse,
    Bearing,
    BearingKind,
    CandidateProposal,
    CommitmentSignatureView,
)
from sanuvia.domain import (
    VOICE_SANUVIA_WORKING_READING,
    ClaimClass,
    EvidenceClass,
    GovernedOutcome,
    GovernedRejection,
    IdentityOutcome,
    ModelBoundary,
    Stance,
)

from sanuvia_phase1.failures import MalformedOutputError
from sanuvia_phase1.identity_resolvers import (
    RESOLVER_ID,
    ExternalIdentityResolver,
    IdentityResolutionPrompt,
)

SUBJECT = "subject-r1"


def _ev(text: str) -> EvidenceInput:
    return EvidenceInput(
        subject_id=SUBJECT, evidence_class=EvidenceClass.NARRATIVE, content=text,
        source="extractor:test", reliability=0.8, classification_confidence=0.9,
    )


class _ProposesStatements:
    """Appraiser proposing one statement per observation, in order."""

    def __init__(self, *statements: str, stance: Stance = Stance.OPEN,
                 claim_class: ClaimClass = ClaimClass.INTERPRETATION) -> None:
        self._statements = list(statements)
        self._stance, self._claim_class = stance, claim_class
        self.calls = 0

    def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
        statement = self._statements[min(self.calls, len(self._statements) - 1)]
        self.calls += 1
        signature = CommitmentSignatureView(
            subject=request.participants[0] if request.participants else "p1",
            attribution=VOICE_SANUVIA_WORKING_READING,
            claim_class=self._claim_class,
            stance=self._stance,
        )
        return AppraisalResponse(
            proposals=(CandidateProposal(f"c{self.calls}", statement, signature),)
        )


def _reply(outcome: str, *, ref: str | None = None, rationale: str = "because",
           confidence: float = 0.7) -> str:
    return json.dumps({
        "outcome": outcome, "matched_ref": ref,
        "rationale": rationale, "confidence": confidence,
    })


class _RecordingClient:
    """Fake resolver client: records the prompt, returns a fixed reply."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.prompts: list[Any] = []

    def __call__(self, prompt: IdentityResolutionPrompt) -> str:
        self.prompts.append(prompt)
        return self.reply


def _run(
    appraiser: Any, client: Any, texts: tuple[str, ...] = ("first", "second")
) -> tuple[Any, Any]:
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store, appraiser=appraiser,
        ids=SequentialIdGenerator(), clock=ManualClock(),
        identity_resolver=ExternalIdentityResolver(client=client),
    )
    service = ReasoningService(deps)
    for text in texts:
        service.record_interaction(SUBJECT, [_ev(text)])
    return store, deps


# --- 1. exact duplicate bypasses the resolver --------------------------------


def test_exact_duplicate_never_reaches_the_resolver() -> None:
    """Case 2 is deterministic: an exact duplicate must not cost a model call."""
    client = _RecordingClient(_reply("distinct_new"))
    store, _ = _run(_ProposesStatements("the same reading", "the same reading"),
                    client)

    assert client.prompts == [], "the resolver was consulted for an exact match"
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    (hypothesis,) = store.hypotheses.list_for_subject(SUBJECT)
    assert hypothesis.supporting_evidence_ids == ("evidence-1", "evidence-2")


# --- 2. plausible non-exact candidate reaches R1, with bounded inputs --------


def test_plausible_non_exact_candidate_reaches_the_resolver() -> None:
    client = _RecordingClient(_reply("ambiguous_review_required"))
    _run(_ProposesStatements("the first reading", "a different reading"), client)

    assert len(client.prompts) == 1
    prompt = client.prompts[0]
    assert prompt.candidate_statement == "a different reading"
    assert len(prompt.existing) == 1
    assert prompt.existing[0].statement == "the first reading"


def test_resolver_receives_no_durable_identifier() -> None:
    """Bounded inputs carry resolution-scoped refs, never a HypothesisId."""
    client = _RecordingClient(_reply("ambiguous_review_required"))
    store, _ = _run(_ProposesStatements("the first reading", "a different reading"),
                    client)

    (lineage,) = store.lineages.list_for_subject(SUBJECT)
    prompt = client.prompts[0]
    rendered = " ".join(
        f"{c.ref} {c.statement}" for c in prompt.existing
    ) + f" {prompt.candidate_subject} {prompt.candidate_statement}"

    assert str(lineage.hypothesis_id) not in rendered
    assert {c.ref for c in prompt.existing} == {"C1"}


# --- 3-6. the four governed outcomes -----------------------------------------


def test_resolver_match_existing_attaches_to_the_lineage() -> None:
    store, _ = _run(
        _ProposesStatements("the first reading", "a restated reading"),
        _RecordingClient(_reply("match_existing", ref="C1")),
    )
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    (hypothesis,) = store.hypotheses.list_for_subject(SUBJECT)
    assert hypothesis.supporting_evidence_ids == ("evidence-1", "evidence-2")


def test_resolver_refine_existing_appends_a_statement_version() -> None:
    """The same commitment, clarified: no new lineage, a new version."""
    store, _ = _run(
        _ProposesStatements("the first reading", "the first reading, specifically"),
        _RecordingClient(_reply("refine_existing", ref="C1")),
    )
    (lineage,) = store.lineages.list_for_subject(SUBJECT)
    versions = list(store.statement_versions.history(lineage.hypothesis_id))

    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    assert [v.statement for v in versions] == [
        "the first reading", "the first reading, specifically",
    ], "appended, never overwriting the prior statement (F-2)"


def test_refined_lineage_still_matches_its_earlier_statement() -> None:
    """F-2: a re-presented earlier statement identifies the lineage, not a duplicate."""
    client = _RecordingClient(_reply("refine_existing", ref="C1"))
    store, _ = _run(
        _ProposesStatements(
            "the first reading", "the first reading, specifically", "the first reading",
        ),
        client,
        texts=("first", "second", "third"),
    )
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    # The third proposal matched exactly, so it never reached the resolver.
    assert len(client.prompts) == 1


def test_resolver_distinct_new_founds_a_second_lineage() -> None:
    store, _ = _run(
        _ProposesStatements("the first reading", "a genuinely different reading"),
        _RecordingClient(_reply("distinct_new")),
    )
    lineages = store.lineages.list_for_subject(SUBJECT)
    assert len(lineages) == 2
    assert len({l.lineage_key for l in lineages}) == 1, "same bound, two lineages"


def test_resolver_ambiguous_parks_the_candidate() -> None:
    store, _ = _run(
        _ProposesStatements("the first reading", "an unclear reading"),
        _RecordingClient(_reply("ambiguous_review_required")),
    )
    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    (parked,) = store.identity_adjudications.list_for_subject(SUBJECT)
    assert parked.decision.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    assert parked.candidate_statement == "an unclear reading"


# --- 7. invalid resolver output is a governed failure ------------------------


@pytest.mark.parametrize("payload", [
    '{"outcome": "invented_outcome", "matched_ref": null, "rationale": "r", "confidence": 0.5}',
    '{"outcome": "match_existing", "matched_ref": null, "rationale": "r", "confidence": 0.5}',
    '{"matched_ref": null, "rationale": "r", "confidence": 0.5}',
    '{"outcome": "distinct_new", "matched_ref": null, "rationale": "", "confidence": 0.5}',
    '{"outcome": "distinct_new", "matched_ref": null, "rationale": "r", "confidence": 9}',
    "not json at all",
])
def test_malformed_resolver_output_is_rejected_not_repaired(payload: str) -> None:
    """F-7 (d): a GOVERNED failure. Never repaired, never defaulted.

    This previously accepted either exception class, which let a
    MalformedOutputError escape the service and leave no governed rejected-plan
    record at all. The governed outcome is now required.
    """
    with pytest.raises(GovernedRejection) as exc:
        _run(_ProposesStatements("the first reading", "a different reading"),
             _RecordingClient(payload))

    assert exc.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert exc.value.boundary is ModelBoundary.IDENTITY_RESOLVER
    assert exc.value.raw_response == payload, "the exact reply is preserved"
    assert dict(exc.value.provenance)["resolver_id"] == RESOLVER_ID


@pytest.mark.parametrize("unoffered", ["C99", "hyp-1", "hyp-9"])
def test_resolver_reference_vocabulary_is_closed(unoffered: str) -> None:
    """The reply may name only the refs THIS request offered.

    Checked against the offered set, not against durable-store membership. The
    distinction matters: "hyp-1" names a real lineage, and a membership test
    would have accepted it even though the request offered only C1.
    """
    with pytest.raises(GovernedRejection) as exc:
        _run(_ProposesStatements("the first reading", "a different reading"),
             _RecordingClient(_reply("match_existing", ref=unoffered)))

    assert exc.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert exc.value.boundary is ModelBoundary.IDENTITY_RESOLVER
    assert "was not offered" in str(exc.value)


def test_resolver_failure_preserves_the_resolver_raw_response() -> None:
    """Provenance survives the rejection (§4, F-7 d)."""
    reply = _reply("match_existing", ref="C99")
    with pytest.raises(GovernedRejection) as exc:
        _run(_ProposesStatements("the first reading", "a different reading"),
             _RecordingClient(reply))
    assert exc.value.raw_response == reply


# --- 8. the resolver cannot supply durable identity --------------------------


def test_resolver_cannot_assign_durable_identity_with_distinct_new() -> None:
    """DISTINCT_NEW founds a lineage, so it must not name one.

    The claim is unchanged; only where it is enforced moved (A-1). This is now
    caught at the adapter's validation boundary, where the resolver's full
    provenance is available, so the assertion is on the governed outcome and
    the stated reason rather than on one layer's wording.
    """
    with pytest.raises(GovernedRejection) as exc:
        _run(_ProposesStatements("the first reading", "a different reading"),
             _RecordingClient(_reply("distinct_new", ref="C1")))

    assert exc.value.outcome is GovernedOutcome.INVALID_APPRAISAL_RESPONSE
    assert exc.value.boundary is ModelBoundary.IDENTITY_RESOLVER
    assert "engine issues its durable identity" in str(exc.value)
    # And the rejection now carries the complete resolver provenance.
    assert set(dict(exc.value.provenance)) == {
        "resolver_id", "prompt_version", "schema_version",
    }


def test_engine_issues_the_durable_id_for_a_resolver_distinct_new() -> None:
    """The resolver decides sameness; the ENGINE issues the identifier."""
    store, _ = _run(
        _ProposesStatements("the first reading", "a genuinely different reading"),
        _RecordingClient(_reply("distinct_new")),
    )
    ids = {l.hypothesis_id for l in store.lineages.list_for_subject(SUBJECT)}
    assert ids == {"hyp-1", "hyp-2"}, "engine-issued, sequential"


# --- 9. attribution is untouched by resolution -------------------------------


def test_attribution_remains_the_governed_voice_label() -> None:
    for reply in (_reply("distinct_new"), _reply("refine_existing", ref="C1")):
        store, _ = _run(
            _ProposesStatements("the first reading", "a second reading"),
            _RecordingClient(reply),
        )
        attributions = {
            l.attribution for l in store.lineages.list_for_subject(SUBJECT)
        }
        assert attributions == {VOICE_SANUVIA_WORKING_READING}


# --- 10. unresolved candidates stay parked -----------------------------------


def test_parked_candidate_creates_no_hypothesis_and_is_preserved() -> None:
    store, _ = _run(
        _ProposesStatements("the first reading", "an unclear reading"),
        _RecordingClient(_reply("ambiguous_review_required", confidence=0.05)),
    )
    assert len(store.hypotheses.list_for_subject(SUBJECT)) == 1
    (parked,) = store.identity_adjudications.list_for_subject(SUBJECT)
    assert parked.plausible_matches, "plausible candidates are not discarded"
    # Confidence is provenance only (F-8): a low value parks nothing by itself
    # and rewrites no outcome.
    assert parked.decision.confidence == 0.05
    assert parked.decision.resolver_id == RESOLVER_ID
    assert parked.decision.resolver_raw_response is not None


def test_low_confidence_does_not_rewrite_a_returned_outcome() -> None:
    """F-8: no threshold, no minimum, no confidence-based parking."""
    store, _ = _run(
        _ProposesStatements("the first reading", "a second reading"),
        _RecordingClient(_reply("distinct_new", confidence=0.01)),
    )
    assert len(store.lineages.list_for_subject(SUBJECT)) == 2
    assert store.identity_adjudications.list_for_subject(SUBJECT) == []


# --- 11. R1a: stance inversion is not refinement -----------------------------


class _InvertsOnSecond:
    """Proposes AFFIRMS, then the same bound with NEGATES.

    The second response also carries the structured ``CONTRADICTS`` bearing on
    the existing lineage. That is required independently of identity: check 10
    (ruling Q5) rejects a plan whose candidate inverts an active lineage's
    stance without the structured contradiction operation, whatever the
    identity outcome turns out to be. Supplying it isolates the R1a override as
    the thing under test rather than check 10.
    """

    def __init__(self) -> None:
        self.calls = 0

    def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
        self.calls += 1
        stance = Stance.AFFIRMS if self.calls == 1 else Stance.NEGATES
        statement = (
            "the partner withdraws" if self.calls == 1
            else "the partner does not withdraw"
        )
        signature = CommitmentSignatureView(
            subject=request.participants[0] if request.participants else "p1",
            attribution=VOICE_SANUVIA_WORKING_READING,
            claim_class=ClaimClass.INTERPRETATION, stance=stance,
        )
        bearings = tuple(
            Bearing(view.handle, BearingKind.CONTRADICTS) for view in request.existing
        )
        return AppraisalResponse(
            proposals=(CandidateProposal(f"c{self.calls}", statement, signature),),
            bearings=bearings,
        )


@pytest.mark.parametrize("merge_outcome", ["refine_existing", "match_existing"])
def test_inverted_stance_merge_outcomes_are_discarded_under_r1a(merge_outcome: str) -> None:
    """C-1: both merge outcomes are discarded; the candidate parks instead."""
    store, _ = _run(_InvertsOnSecond(),
                    _RecordingClient(_reply(merge_outcome, ref="C1")))

    assert len(store.lineages.list_for_subject(SUBJECT)) == 1, "no merge, no lineage"
    (parked,) = store.identity_adjudications.list_for_subject(SUBJECT)
    assert parked.decision.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    # What the resolver actually said is preserved, so the discard is auditable.
    assert parked.decision.overridden_resolver_outcome is not None
    assert parked.decision.overridden_resolver_outcome.value == merge_outcome.upper()
    assert "R1a" in (parked.decision.rationale or "")


def test_inverted_stance_distinct_new_is_not_overridden() -> None:
    """D-2: the override is NARROW. DISTINCT_NEW is not a merge outcome.

    It stands and founds a second lineage. The old all-inversions-park
    behaviour would have parked it instead.
    """
    store, _ = _run(_InvertsOnSecond(), _RecordingClient(_reply("distinct_new")))

    assert len(store.lineages.list_for_subject(SUBJECT)) == 2
    assert store.identity_adjudications.list_for_subject(SUBJECT) == []


def test_inverted_stance_distinct_new_still_faces_check_10() -> None:
    """D-2: ... and remains subject to the normal subsequent validation.

    Without the structured CONTRADICTS operation the plan fails check 10, so
    an inverted-stance DISTINCT_NEW is not a way around the contradiction
    requirement.
    """
    class _InvertsWithoutContradicts(_InvertsOnSecond):
        def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
            response = super().appraise(request)
            return AppraisalResponse(proposals=response.proposals, bearings=())

    with pytest.raises(GovernedRejection) as exc:
        _run(_InvertsWithoutContradicts(), _RecordingClient(_reply("distinct_new")))
    assert exc.value.outcome is GovernedOutcome.INVALID_CONTRADICTION_PLAN


def test_inverted_stance_ambiguous_is_not_overridden() -> None:
    """D-2: a resolver AMBIGUOUS_REVIEW_REQUIRED also stands as returned."""
    store, _ = _run(_InvertsOnSecond(),
                    _RecordingClient(_reply("ambiguous_review_required")))
    (parked,) = store.identity_adjudications.list_for_subject(SUBJECT)
    assert parked.decision.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED
    # Not an override: the resolver returned this itself.
    assert parked.decision.overridden_resolver_outcome is None


# --- 12. no resolver outside the approved integration ------------------------


def test_no_resolver_is_configured_by_default() -> None:
    """The real path gets R1 only where it is explicitly wired."""
    from sanuvia.adapters.reasoning import ScriptedAppraiser

    deps = build_in_memory_dependencies(appraiser=ScriptedAppraiser({}))
    assert deps.identity_resolver is None


def test_without_a_resolver_a_non_exact_candidate_still_parks() -> None:
    """Reading A is unchanged where R1 is not wired."""
    store = InMemoryReasoningStore()
    deps = build_in_memory_dependencies(
        store=store, appraiser=_ProposesStatements("the first", "a second"),
        ids=SequentialIdGenerator(), clock=ManualClock(),
    )
    service = ReasoningService(deps)
    service.record_interaction(SUBJECT, [_ev("first")])
    service.record_interaction(SUBJECT, [_ev("second")])

    assert len(store.lineages.list_for_subject(SUBJECT)) == 1
    assert len(store.identity_adjudications.list_for_subject(SUBJECT)) == 1
