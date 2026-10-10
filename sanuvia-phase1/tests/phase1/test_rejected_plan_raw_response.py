"""Rejected-plan audit must carry what the appraiser returned (§5.7, §5.8, F-15).

Steps 6 and 8 reject through ``HandleTable``, which has no access to the
appraisal response, and the ``AppraisedObservation`` that would hold it is only
appended once both steps succeed. A rejection there therefore lost the model's
words entirely -- precisely the unknown-reference family, which is the headline
rejection.

Driven through the real trajectory boundary (``SanuviaPersistentCondition``),
not a lower-level unit, because that is where §5.8 places the requirement.

Fake clients only. No provider, no network, no model inference, no Case 001
tuning, no protected evidence touched.
"""

from __future__ import annotations

from typing import Any

import json

import pytest

from fixtures.longitudinal.case_001 import CASE_001

from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.evidence_appraisers.external import ExternalEvidenceAppraiser
from sanuvia_phase1.trajectory import InteractionOutcome

#: An appraisal naming a hypothesis handle this request never issued.
UNKNOWN_HANDLE_REPLY = json.dumps(
    {"supports": ["req-1::H99"], "contradicts": [], "proposals": []}
)


def _proposal_reply(prompt: Any, *, statement: str) -> str:
    """A well-formed v3 proposal, using a label the prompt actually supplied."""
    return json.dumps({
        "supports": [], "contradicts": [],
        "proposals": [{
            "local_ref": "p1",
            "statement": statement,
            "signature": {
                "subject": prompt.participants[0],
                "claim_class": "interpretation",
                "stance": "open",
                "temporal_scope": None,
            },
        }],
    })


def _single_record_interaction() -> Any:
    return next(i for i in CASE_001.interactions if len(CASE_001.evidence_refs(i)) == 1)


def _multi_record_interaction() -> Any:
    return next(i for i in CASE_001.interactions if len(CASE_001.evidence_refs(i)) > 1)


# --- Test A: single-record unknown reference --------------------------------


def _run_single_record_rejection() -> tuple[Any, Any]:
    condition = SanuviaPersistentCondition(
        CASE_001,
        appraiser=ExternalEvidenceAppraiser(client=lambda _p: UNKNOWN_HANDLE_REPLY),
    )
    condition.start()
    return condition, condition.step(_single_record_interaction())


def test_single_record_rejection_preserves_the_raw_appraiser_response() -> None:
    """The defect: raw was '' for the unknown-reference family."""
    _, record = _run_single_record_rejection()

    assert record.appraisal_responses == (("evidence-1", UNKNOWN_HANDLE_REPLY),)
    # The exact reply, not merely something non-empty.
    assert record.appraisal_responses[0][1] == UNKNOWN_HANDLE_REPLY


def test_single_record_rejection_keeps_the_governed_shape() -> None:
    """§5.7: outcome, governed failure and committed:false are unchanged."""
    _, record = _run_single_record_rejection()

    assert record.outcome is InteractionOutcome.REJECTED_PLAN
    assert record.governed_failure == "UNKNOWN_HYPOTHESIS_REFERENCE"
    assert record.committed is False


def test_single_record_rejection_keeps_the_admitted_observations() -> None:
    _, record = _run_single_record_rejection()
    assert record.ingested_evidence_ids == CASE_001.evidence_refs(
        _single_record_interaction()
    )


def test_single_record_rejection_still_rolls_reasoning_state_back() -> None:
    """Rollback semantics are untouched: audit gained data, state did not."""
    condition, record = _run_single_record_rejection()
    assert condition._store is not None  # start() ran
    assert condition._store is not None  # start() ran
    store = condition._store

    assert store.evidence.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []
    assert store.hypotheses.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []
    assert store.lineages.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []
    assert record.hypotheses == ()
    assert record.predictions == ()
    assert record.revision_events == ()


def test_single_record_raw_echo_embeds_the_response() -> None:
    """``raw`` stays a canonical JSON echo, as on every other record."""
    _, record = _run_single_record_rejection()
    echoed = json.loads(record.raw)

    assert echoed["outcome"] == "rejected_plan"
    assert echoed["governed_failure"] == "UNKNOWN_HYPOTHESIS_REFERENCE"
    assert echoed["committed"] is False
    assert echoed["appraisal_responses"] == [
        {"evidence_id": "evidence-1", "raw_response": UNKNOWN_HANDLE_REPLY}
    ]


# --- Test B: later failure in a multi-record interaction --------------------


class _SucceedsThenReferencesUnknown:
    """First appraisal proposes normally; the second names an unknown handle."""

    def __init__(self) -> None:
        self.calls = 0
        self.replies: list[str] = []

    def __call__(self, prompt: Any) -> str:
        self.calls += 1
        reply = (
            _proposal_reply(prompt, statement="an accepted first reading")
            if self.calls == 1
            else UNKNOWN_HANDLE_REPLY
        )
        self.replies.append(reply)
        return reply


def _run_multi_record_rejection() -> tuple[Any, Any, Any]:
    client = _SucceedsThenReferencesUnknown()
    condition = SanuviaPersistentCondition(
        CASE_001, appraiser=ExternalEvidenceAppraiser(client=client)
    )
    condition.start()
    record = condition.step(_multi_record_interaction())
    return condition, record, client


def test_multi_record_rejection_is_a_rejected_plan() -> None:
    _, record, client = _run_multi_record_rejection()
    assert client.calls == 2, "both observations were appraised"
    assert record.outcome is InteractionOutcome.REJECTED_PLAN
    assert record.committed is False


def test_multi_record_rejection_retains_the_earlier_response() -> None:
    """The point of the ordered carrier.

    A single ``raw_response`` field would show only the failing call, so the
    first observation's response -- which the appraiser did return, and which a
    reviewer needs to interpret the interaction -- would vanish because a LATER
    record rejected.
    """
    _, record, client = _run_multi_record_rejection()

    responses = record.appraisal_responses
    assert len(responses) == 2

    earlier_raw = responses[0][1]
    assert earlier_raw == client.replies[0]
    assert "an accepted first reading" in earlier_raw


def test_multi_record_rejection_retains_the_failing_response() -> None:
    _, record, client = _run_multi_record_rejection()
    assert record.appraisal_responses[1][1] == UNKNOWN_HANDLE_REPLY == client.replies[1]


def test_multi_record_responses_are_ordered_and_attributable() -> None:
    """Each response names the observation it answered, in call order."""
    _, record, _ = _run_multi_record_rejection()

    evidence_ids = [evidence_id for evidence_id, _ in record.appraisal_responses]
    assert evidence_ids == ["evidence-1", "evidence-2"], "call order, attributed"
    # Attribution is per-observation, so the two are distinguishable.
    assert len(set(evidence_ids)) == 2


def test_multi_record_rejection_is_deterministic() -> None:
    """Same inputs, same ordered audit."""
    first = _run_multi_record_rejection()[1].appraisal_responses
    second = _run_multi_record_rejection()[1].appraisal_responses
    assert first == second


def test_multi_record_rejection_still_rolls_reasoning_state_back() -> None:
    """The earlier appraisal SUCCEEDED and founded a lineage in the plan.

    It must still not survive: the interaction was rejected, so the earlier
    record's reasoning state goes with it even though its audit does not.
    That is the TD-18 distinction, exercised where it is easiest to get wrong.
    """
    condition, record, _ = _run_multi_record_rejection()
    assert condition._store is not None  # start() ran
    assert condition._store is not None  # start() ran
    store = condition._store

    assert store.evidence.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []
    assert store.hypotheses.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []
    assert store.lineages.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []
    assert record.hypotheses == ()


def test_a_committed_interaction_records_no_appraisal_responses() -> None:
    """The carrier is the rejected-plan audit, not a general response log."""
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()
    record = condition.step(_single_record_interaction())

    assert record.outcome is InteractionOutcome.COMMITTED
    assert record.appraisal_responses == ()


def test_a_no_evidence_hold_records_no_appraisal_responses() -> None:
    """A hold makes no appraisal call, so there is nothing to carry (§5.7)."""
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()
    hold = next(i for i in CASE_001.interactions if not CASE_001.evidence_refs(i))
    record = condition.step(hold)

    assert record.outcome is InteractionOutcome.NO_EVIDENCE_HOLD
    assert record.appraisal_responses == ()
