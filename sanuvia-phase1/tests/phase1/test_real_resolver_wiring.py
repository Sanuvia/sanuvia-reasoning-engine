"""The external identity resolver, wired through the REAL condition and caller.

``test_r1_identity_resolver`` exercises the resolver against a hand-built
dependency bundle. That proves the adapter, not the wiring: until now nothing
constructed an ``ExternalIdentityResolver`` through
``SanuviaPersistentCondition`` or ``run_transcript_demonstration``, so the real
path could only ever reach §2 G case 4 with ``resolver=None`` and park.

These tests trace the actual construction path -- configuration, caller,
condition, dependency bundle, adjudicator -- and assert the resolver is invoked
at the correct boundary with the correct bounded inputs, that its accepted
outcomes keep their accepted behaviour, and that a malformed answer is still a
governed rejection with complete provenance and a complete rollback.

Fake clients only. No provider is selected and nothing reaches a network.
"""

from __future__ import annotations

from typing import Any

import json

import pytest

from fixtures.offline_real import OFFLINE_PARTICIPANTS, offline_real_config

from sanuvia.adapters.persistence.in_memory import InMemoryReasoningStore
from sanuvia.adapters.reasoning import ScriptedAppraiser
from sanuvia.adapters.reasoning.scripted_identity_resolver import (
    ScriptedIdentityResolver,
)
from sanuvia.application.ports.reasoning import (
    AppraisalRequest,
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
    IdentityOutcome,
    ModelBoundary,
    Stance,
    shared_space_id,
)

from sanuvia_phase1 import pipeline
from sanuvia_phase1.case import Case, CaseEvidence, CaseInteraction
from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.evidence_extractors.external import ExternalEvidenceExtractor
from sanuvia_phase1.failures import ConfigurationError
from sanuvia_phase1.identity_resolvers import RESOLVER_ID, ExternalIdentityResolver
from sanuvia_phase1.identity_resolvers.external import PROMPT_VERSION, SCHEMA_VERSION
from sanuvia_phase1.language_models import ExternalLanguageModel
from sanuvia_phase1.runconfig import REAL, validate_run_configuration
from sanuvia_phase1.trajectory import InteractionOutcome

SUBJECT = "subject-wiring"
SPACE = shared_space_id("dyad-wiring")

#: Two statements that share a signature bound but are not an exact match, so
#: §2 G reaches resolution-order case 4 -- the only case the resolver sees.
FIRST = "she withdraws when the evening runs late"
SECOND = "she withdraws when the evening runs late, especially midweek"


# --- the real appraiser side (fake client, no inference) ---------------------


class _ProposesInOrder:
    """A real ``EvidenceAppraiser`` over authored statements. Not scripted:
    it is injected like ``ExternalEvidenceAppraiser`` and so selects the real
    branch of the condition."""

    def __init__(self, *statements: str) -> None:
        self._statements = list(statements)
        self.calls = 0

    def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
        statement = self._statements[min(self.calls, len(self._statements) - 1)]
        self.calls += 1
        signature = CommitmentSignatureView(
            subject=request.participants[0] if request.participants else "p1",
            attribution=VOICE_SANUVIA_WORKING_READING,
            claim_class=ClaimClass.BEHAVIOUR_PATTERN,
            stance=Stance.OPEN,
        )
        return AppraisalResponse(
            proposals=(CandidateProposal(f"c{self.calls}", statement, signature),)
        )


class _RecordingResolverClient:
    """Captures the bounded prompt and returns an authored reply."""

    def __init__(self, reply: str) -> None:
        self._reply = reply
        self.prompts: list[Any] = []

    def __call__(self, prompt: Any) -> str:
        self.prompts.append(prompt)
        return self._reply


class _ReplyPerCall:
    """Returns the next authored reply on each call. One call, one answer --
    the resolver performs no retries, so the sequence is the whole script."""

    def __init__(self, *replies: str) -> None:
        self._replies = list(replies)
        self.calls = 0

    def __call__(self, prompt: Any) -> str:
        reply = self._replies[min(self.calls, len(self._replies) - 1)]
        self.calls += 1
        return reply


def _resolution(
    outcome: str, matched_ref: str | None = None, *, confidence: float = 0.9
) -> str:
    return json.dumps(
        {
            "outcome": outcome,
            "matched_ref": matched_ref,
            "rationale": "authored for the wiring test",
            "confidence": confidence,
        }
    )


# --- the case ----------------------------------------------------------------


def _evidence(n: int) -> CaseEvidence:
    return CaseEvidence(
        ref=f"ER-{n:03d}",
        engine_id=f"evidence-{n}",
        text=f"observation {n}",
        evidence_class=EvidenceClass.NARRATIVE,
        reliability=0.8,
        classification_confidence=0.9,
        provenance_confidence=0.9,
        source="extractor:test",
        evidence_role="",
    )


def _case() -> Case:
    return Case(
        case_id="wiring",
        subject_id=SUBJECT,
        space_id=SPACE,
        interactions=(
            CaseInteraction(1, "seq-1", (_evidence(1),)),
            CaseInteraction(2, "seq-2", (_evidence(2),)),
        ),
        appraisal_script={},
        hypothesis_catalogue={},
    )


def _run_condition(
    client: _RecordingResolverClient,
) -> tuple[SanuviaPersistentCondition, tuple[Any, ...]]:
    condition = SanuviaPersistentCondition(
        _case(),
        appraiser=_ProposesInOrder(FIRST, SECOND),
        identity_resolver=ExternalIdentityResolver(client),
    )
    condition.start()
    records = tuple(condition.step(i) for i in _case().interactions)
    return condition, records


def _store_of(condition: SanuviaPersistentCondition) -> InMemoryReasoningStore:
    assert condition._store is not None  # start() ran
    return condition._store


def _adjudications(condition: SanuviaPersistentCondition) -> tuple[Any, ...]:
    return tuple(
        _store_of(condition).identity_adjudications.list_for_subject(
            SUBJECT, space_id=SPACE
        )
    )


def _counts(condition: SanuviaPersistentCondition) -> dict[str, int]:
    """Rows per store for this subject, over the WHOLE bundle.

    Enumerated from the bundle rather than a hard-coded list, so a store added
    later is covered without this test being edited (N-1).
    """
    counts: dict[str, int] = {}
    for name, member in bundle_stores(_store_of(condition)).items():
        lister = getattr(member, "list_for_subject", None)
        if lister is None:
            continue
        counts[name] = len(tuple(lister(SUBJECT, space_id=SPACE)))
    return counts


# --- 1. the resolver is actually constructed and reached ---------------------


def test_the_condition_wires_the_injected_resolver_into_the_bundle() -> None:
    """The construction path, asserted where it ends: the dependency bundle."""
    resolver = ExternalIdentityResolver(_RecordingResolverClient(_resolution("distinct_new")))
    condition = SanuviaPersistentCondition(
        _case(), appraiser=_ProposesInOrder(FIRST), identity_resolver=resolver
    )
    condition.start()

    assert condition._service is not None
    assert condition._service._deps.identity_resolver is resolver


def test_the_resolver_is_invoked_at_case_four_and_only_there() -> None:
    """Cases 1-3 never reach it: the first interaction founds the lineage with
    no plausible candidate, so only the second consults the resolver."""
    client = _RecordingResolverClient(_resolution("distinct_new"))
    _run_condition(client)

    assert len(client.prompts) == 1, "one call for the one non-exact candidate"


def test_the_resolver_receives_bounded_inputs_and_no_durable_identifier() -> None:
    """§2 G bounded inputs, asserted on the prompt that actually crossed."""
    client = _RecordingResolverClient(_resolution("distinct_new"))
    condition, _ = _run_condition(client)
    (prompt,) = client.prompts

    assert prompt.candidate_statement == SECOND
    assert [c.ref for c in prompt.existing] == ["C1"]
    assert prompt.existing[0].statement == FIRST
    # No durable identity crosses: the offered ref is resolution-scoped.
    rendered = json.dumps(
        {"c": prompt.candidate_statement,
         "e": [(c.ref, c.statement) for c in prompt.existing]}
    )
    for lineage in _store_of(condition).lineages.list_for_subject(SUBJECT, space_id=SPACE):
        assert str(lineage.hypothesis_id) not in rendered


# --- 2. accepted outcomes keep their accepted behaviour ----------------------


def test_refine_existing_is_accepted_and_appends_a_statement_version() -> None:
    client = _RecordingResolverClient(_resolution("refine_existing", "C1"))
    condition, records = _run_condition(client)

    assert records[1].outcome is not InteractionOutcome.REJECTED_PLAN
    lineages = _store_of(condition).lineages.list_for_subject(SUBJECT, space_id=SPACE)
    assert len(lineages) == 1, "a refinement attaches, it does not found a lineage"
    history = _store_of(condition).statement_versions.history(lineages[0].hypothesis_id)
    assert [v.statement for v in history] == [FIRST, SECOND]


def test_ambiguous_review_required_parks_without_creating_a_lineage() -> None:
    client = _RecordingResolverClient(_resolution("ambiguous_review_required"))
    condition, records = _run_condition(client)

    assert records[1].outcome is not InteractionOutcome.REJECTED_PLAN
    assert len(_store_of(condition).lineages.list_for_subject(SUBJECT, space_id=SPACE)) == 1
    parked = _adjudications(condition)
    assert len(parked) == 1
    assert parked[0].decision.outcome is IdentityOutcome.AMBIGUOUS_REVIEW_REQUIRED


def test_distinct_new_founds_a_second_lineage() -> None:
    client = _RecordingResolverClient(_resolution("distinct_new"))
    condition, _ = _run_condition(client)

    assert len(_store_of(condition).lineages.list_for_subject(SUBJECT, space_id=SPACE)) == 2


def test_the_decision_carries_the_resolver_provenance() -> None:
    client = _RecordingResolverClient(_resolution("ambiguous_review_required"))
    condition, _ = _run_condition(client)
    (parked,) = _adjudications(condition)

    assert parked.decision.resolver_id == RESOLVER_ID
    assert parked.decision.resolver_raw_response is not None
    assert "ambiguous_review_required" in parked.decision.resolver_raw_response


# --- 3. malformed and invalid answers stay governed rejections ---------------


@pytest.mark.parametrize(
    "reply",
    [
        "not json at all",
        json.dumps({"outcome": "merge_them", "matched_ref": None,
                    "rationale": "r", "confidence": 0.5}),
        json.dumps({"outcome": "match_existing", "matched_ref": "C9",
                    "rationale": "r", "confidence": 0.5}),
        json.dumps({"outcome": "match_existing", "matched_ref": None,
                    "rationale": "r", "confidence": 0.5}),
        json.dumps({"outcome": "distinct_new", "matched_ref": "C1",
                    "rationale": "r", "confidence": 0.5}),
    ],
)
def test_an_unusable_answer_is_a_governed_rejection_through_the_condition(
    reply: str,
) -> None:
    """Malformed output, an outcome outside the vocabulary, an unoffered ref,
    and the two shape rules -- all refused, none repaired."""
    client = _RecordingResolverClient(reply)
    _, records = _run_condition(client)

    assert records[1].outcome is InteractionOutcome.REJECTED_PLAN


def test_the_rejection_carries_the_boundary_and_the_resolver_provenance() -> None:
    client = _RecordingResolverClient("not json at all")
    _, records = _run_condition(client)
    record = records[1]

    assert record.governed_failure == GovernedOutcome.INVALID_APPRAISAL_RESPONSE.name
    assert record.boundary == ModelBoundary.IDENTITY_RESOLVER.name
    provenance = dict(record.boundary_provenance)
    assert provenance["resolver_id"] == RESOLVER_ID
    assert provenance["prompt_version"] == PROMPT_VERSION
    assert provenance["schema_version"] == SCHEMA_VERSION
    # Kept separate from the appraisal responses: both are needed to read the
    # rejection, and a resolver failure must not overwrite the appraiser's words.
    assert record.boundary_raw_response == "not json at all"
    assert record.committed is False


def test_a_rejected_resolution_rolls_back_every_store_in_the_bundle() -> None:
    """Atomicity over the WHOLE bundle, not a sampled store.

    Interaction 1's committed state survives untouched; interaction 2 leaves
    nothing anywhere -- not even the evidence it was admitted with, because
    evidence admission is part of the plan and not a precondition of it.
    """
    committed, _ = _run_condition(
        _RecordingResolverClient(_resolution("distinct_new"))
    )
    rejected, records = _run_condition(_RecordingResolverClient("not json at all"))

    assert records[1].outcome is InteractionOutcome.REJECTED_PLAN
    after, control = _counts(rejected), _counts(committed)

    assert after["lineages"] == 1 and control["lineages"] == 2
    assert after["evidence"] == 1, "the rejected interaction's evidence is gone too"
    assert after["identity_adjudications"] == 0
    # Nothing anywhere in the bundle exceeds what one interaction can produce.
    for name, count in after.items():
        assert count <= control[name], f"{name} grew on a rejected interaction"


def test_a_rejected_resolution_rolls_back_the_identifier_counters() -> None:
    """F-6: identifier allocation sits INSIDE the rollback boundary.

    A third interaction after the rejection must be issued ``evidence-2``. If
    the counter had survived the rejected interaction it would be ``evidence-3``
    -- a gap that a store-only atomicity check cannot see.
    """
    condition = SanuviaPersistentCondition(
        _case(),
        appraiser=_ProposesInOrder(FIRST, SECOND, FIRST),
        identity_resolver=ExternalIdentityResolver(
            # Interaction 1 founds the lineage at case 3 and consults NOBODY,
            # so the resolver's first call belongs to interaction 2.
            _ReplyPerCall(
                "not json at all",                    # interaction 2: rejected
                _resolution("match_existing", "C1"),  # interaction 3: commits
            )
        ),
    )
    condition.start()
    interactions = (*_case().interactions, CaseInteraction(3, "seq-3", (_evidence(3),)))
    records = tuple(condition.step(i) for i in interactions)

    assert records[1].outcome is InteractionOutcome.REJECTED_PLAN
    assert records[2].outcome is not InteractionOutcome.REJECTED_PLAN
    ids = [
        str(r.id)
        for r in _store_of(condition).evidence.list_for_subject(SUBJECT, space_id=SPACE)
    ]
    assert ids == ["evidence-1", "evidence-2"], "the counter was restored, not advanced"


# --- 4. the real caller ------------------------------------------------------


def _transcript_run(resolver: Any, config: Any) -> Any:
    from sanuvia_phase1.transcript import Transcript, TranscriptInteraction

    transcript = Transcript(
        "t-wire",
        SUBJECT,
        SPACE,
        (
            TranscriptInteraction(1, "seq-1", "it ran late", speaker="pA"),
            TranscriptInteraction(2, "seq-2", "it ran late midweek", speaker="pA"),
        ),
    )
    extraction = json.dumps(
        {"evidence": [{"observation": "it ran late", "evidence_class": "narrative",
                       "reliability": 0.8, "classification_confidence": 0.9,
                       "provenance_confidence": 0.9, "text_span": None}]}
    )
    return pipeline.run_transcript_demonstration(
        transcript,
        ExternalEvidenceExtractor(
            lambda _r: extraction, permitted_participants=OFFLINE_PARTICIPANTS
        ),
        {},
        {},
        ExternalLanguageModel(lambda _r: "{}"),
        ExternalLanguageModel(lambda _r: "{}"),
        case_id="wire",
        mode=REAL,
        appraiser=_ProposesInOrder(FIRST, SECOND),
        config=config,
        identity_resolver=resolver,
    )


def test_the_real_caller_passes_the_resolver_through_to_the_boundary() -> None:
    """End to end through ``run_transcript_demonstration``: the resolver the
    caller configured is the one that gets consulted."""
    client = _RecordingResolverClient(_resolution("distinct_new"))
    _transcript_run(
        ExternalIdentityResolver(client),
        offline_real_config(identity_resolution=True),
    )

    assert len(client.prompts) == 1


def test_the_real_caller_still_parks_when_no_resolver_is_configured() -> None:
    """``None`` is a valid REAL configuration, not a degraded one."""
    report = _transcript_run(None, offline_real_config())

    records = report.demonstration.records_by_condition["sanuvia_persistent"]
    assert all(r.outcome is not InteractionOutcome.REJECTED_PLAN for r in records)


# --- 5. the scripted double can never reach a real configuration (G-1) -------


def test_the_condition_refuses_the_fixture_resolver_on_the_real_branch() -> None:
    with pytest.raises(ConfigurationError, match="ScriptedIdentityResolver"):
        SanuviaPersistentCondition(
            _case(),
            appraiser=_ProposesInOrder(FIRST),
            identity_resolver=ScriptedIdentityResolver(),
        )


def test_the_condition_refuses_a_resolver_without_a_real_appraiser() -> None:
    """The branches stay paired: the scripted branch authors its own decisions."""
    with pytest.raises(ConfigurationError, match="without a real appraiser"):
        SanuviaPersistentCondition(
            _case(),
            identity_resolver=ExternalIdentityResolver(
                _RecordingResolverClient(_resolution("distinct_new"))
            ),
        )


def test_the_real_guard_refuses_the_fixture_resolver() -> None:
    with pytest.raises(ConfigurationError, match="ScriptedIdentityResolver"):
        validate_run_configuration(
            REAL,
            extractor=ExternalEvidenceExtractor(
                lambda _r: "{}", permitted_participants=OFFLINE_PARTICIPANTS
            ),
            stateless_model=ExternalLanguageModel(lambda _r: "{}"),
            transcript_model=ExternalLanguageModel(lambda _r: "{}"),
            appraiser=_ProposesInOrder(FIRST),
            config=offline_real_config(identity_resolution=True),
            identity_resolver=ScriptedIdentityResolver(),
        )


def test_the_real_guard_requires_a_spec_for_a_configured_resolver() -> None:
    with pytest.raises(ConfigurationError, match="identity_resolution"):
        validate_run_configuration(
            REAL,
            extractor=ExternalEvidenceExtractor(
                lambda _r: "{}", permitted_participants=OFFLINE_PARTICIPANTS
            ),
            stateless_model=ExternalLanguageModel(lambda _r: "{}"),
            transcript_model=ExternalLanguageModel(lambda _r: "{}"),
            appraiser=_ProposesInOrder(FIRST),
            config=offline_real_config(),
            identity_resolver=ExternalIdentityResolver(
                _RecordingResolverClient(_resolution("distinct_new"))
            ),
        )


def test_the_scripted_branch_still_gets_the_fixture_resolver() -> None:
    """The converse must keep holding: guarding the real branch must not have
    disconnected the golden one."""
    from fixtures.longitudinal.case_001 import CASE_001

    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()

    assert condition._service is not None
    deps = condition._service._deps
    assert isinstance(deps.identity_resolver, ScriptedIdentityResolver)
    assert isinstance(deps.appraiser, ScriptedAppraiser)
