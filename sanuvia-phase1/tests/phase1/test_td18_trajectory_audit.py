"""TD-18 at the trajectory boundary — rejected plan vs hold (§5.7, §5.8).

TD-18 is a distinction between two boundaries, and the trajectory record is
where the design places it. Rejected reasoning STATE does not survive; the
record that the INTERACTION happened does, with different shapes per §5.7.

Fake clients / scripted doubles only.
"""

from __future__ import annotations

from typing import Any

import dataclasses

import pytest

from fixtures.longitudinal.case_001 import CASE_001

from sanuvia.application.ports.reasoning import AppraisalRequest, AppraisalResponse, Bearing, BearingKind
from sanuvia.application.ports.reasoning import HypothesisHandle
from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.trajectory import InteractionOutcome


class _ReferencesUnknownHypothesis:
    """Appraiser that names a handle the request never issued."""

    def appraise(self, request: AppraisalRequest) -> AppraisalResponse:
        return AppraisalResponse(
            bearings=(Bearing(HypothesisHandle("never-issued"), BearingKind.SUPPORTS),)
        )


def _first_with_evidence() -> Any:
    return next(i for i in CASE_001.interactions if CASE_001.evidence_refs(i))


def _hold_interaction() -> Any:
    return next(i for i in CASE_001.interactions if not CASE_001.evidence_refs(i))


def test_rejected_plan_is_recorded_on_the_trajectory_not_raised() -> None:
    """A refused plan is a governed outcome of the interaction, not a crash."""
    condition = SanuviaPersistentCondition(
        CASE_001, appraiser=_ReferencesUnknownHypothesis()
    )
    condition.start()
    record = condition.step(_first_with_evidence())

    assert record.outcome is InteractionOutcome.REJECTED_PLAN
    assert record.governed_failure == "UNKNOWN_HYPOTHESIS_REFERENCE"
    assert record.committed is False


def test_rejected_plan_preserves_the_admitted_observations() -> None:
    """§5.8: the audit carries the observation refs that WERE admitted."""
    condition = SanuviaPersistentCondition(
        CASE_001, appraiser=_ReferencesUnknownHypothesis()
    )
    condition.start()
    interaction = _first_with_evidence()
    record = condition.step(interaction)

    assert record.ingested_evidence_ids == CASE_001.evidence_refs(interaction)
    assert record.ingested_evidence_ids, "evidence was admitted before the refusal"


def test_rejected_plan_leaves_every_reasoning_state_view_empty() -> None:
    """§5.8: reasoning state is unchanged, so every view is empty."""
    condition = SanuviaPersistentCondition(
        CASE_001, appraiser=_ReferencesUnknownHypothesis()
    )
    condition.start()
    record = condition.step(_first_with_evidence())

    assert record.hypotheses == ()
    assert record.predictions == ()
    assert record.inquiry is None
    assert record.revision_events == ()
    assert record.revision_count == 0
    assert record.model_version_id is None


def test_rejected_plan_mutates_no_reasoning_state() -> None:
    """The other half of TD-18: rejected STATE does not survive."""
    condition = SanuviaPersistentCondition(
        CASE_001, appraiser=_ReferencesUnknownHypothesis()
    )
    condition.start()
    condition.step(_first_with_evidence())

    assert condition._store is not None  # start() ran

    assert condition._store is not None  # start() ran

    store = condition._store
    assert store.evidence.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []
    assert store.hypotheses.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []
    assert store.lineages.list_for_subject(
        CASE_001.subject_id, space_id=CASE_001.space_id) == []


def test_rejected_plan_and_no_evidence_hold_are_structurally_distinct() -> None:
    """§5.7: they can never be confused, by shape rather than by flag.

    The hold carries no observations because none were admitted. The rejected
    plan carries them because they were. That is the structural difference the
    design relies on, so it is asserted directly rather than via the flag.
    """
    rejected_condition = SanuviaPersistentCondition(
        CASE_001, appraiser=_ReferencesUnknownHypothesis()
    )
    rejected_condition.start()
    rejected = rejected_condition.step(_first_with_evidence())

    hold_condition = SanuviaPersistentCondition(CASE_001)
    hold_condition.start()
    hold = hold_condition.step(_hold_interaction())

    assert rejected.outcome is InteractionOutcome.REJECTED_PLAN
    assert hold.outcome is InteractionOutcome.NO_EVIDENCE_HOLD

    # Structural: observations present on one, absent on the other.
    assert rejected.ingested_evidence_ids
    assert hold.ingested_evidence_ids == ()

    # Governed outcome named on one, absent on the other.
    assert rejected.governed_failure is not None
    assert hold.governed_failure is None


def test_a_committed_interaction_is_marked_committed() -> None:
    """The third shape: neither refused nor empty."""
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()
    record = condition.step(_first_with_evidence())

    assert record.outcome is InteractionOutcome.COMMITTED
    assert record.committed is True
    assert record.governed_failure is None
    assert record.hypotheses, "a committed interaction has reasoning state"


def test_governed_failure_is_an_outcome_name_not_an_error_message() -> None:
    """Audit carries the governed outcome, not free text."""
    from sanuvia.domain import GovernedOutcome

    condition = SanuviaPersistentCondition(
        CASE_001, appraiser=_ReferencesUnknownHypothesis()
    )
    condition.start()
    record = condition.step(_first_with_evidence())

    assert record.governed_failure in {o.value for o in GovernedOutcome}
