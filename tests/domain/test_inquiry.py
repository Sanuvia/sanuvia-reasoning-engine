"""Inquiry invariants (FR-IQ-001 .. FR-IQ-004)."""

from __future__ import annotations

import pytest

from sanuvia.domain import (
    EvidenceRecordId,
    HypothesisId,
    Inquiry,
    InquiryId,
    InquiryStatus,
    InvariantViolation,
    ModelUncertainty,
)
from tests.conftest import SUBJECT, T0


def _make_inquiry(
    *, hyps: tuple[str, ...], evs: tuple[str, ...], status: InquiryStatus
) -> Inquiry:
    return Inquiry(
        id=InquiryId("inq-1"),
        subject_id=SUBJECT,
        statement="What does the user believe is driving the lateness?",
        status=status,
        activated_hypothesis_ids=tuple(HypothesisId(h) for h in hyps),
        motivating_evidence_ids=tuple(EvidenceRecordId(e) for e in evs),
        current_uncertainty=ModelUncertainty(0.6),
        created_at=T0,
    )


def test_inquiry_must_reference_hypothesis_or_evidence() -> None:
    # Traceability constraint FR-IQ-004: no addressing uncertainty without
    # reference to the hypotheses/evidence that justify it.
    with pytest.raises(InvariantViolation):
        _make_inquiry(hyps=(), evs=(), status=InquiryStatus.PROPOSED)


def test_inquiry_valid_with_only_evidence() -> None:
    inquiry = _make_inquiry(hyps=(), evs=("ev-1",), status=InquiryStatus.ACTIVE)
    assert inquiry.motivating_evidence_ids == (EvidenceRecordId("ev-1"),)


def test_inquiry_valid_with_only_hypothesis() -> None:
    inquiry = _make_inquiry(hyps=("hyp-1",), evs=(), status=InquiryStatus.ACTIVE)
    assert inquiry.activated_hypothesis_ids == (HypothesisId("hyp-1"),)


def test_full_status_vocabulary_is_present() -> None:
    assert {s.name for s in InquiryStatus} == {
        "PROPOSED",
        "ACTIVE",
        "DORMANT",
        "LOCALLY_RESOLVED",
        "REOPENED",
        "SUPERSEDED",
        "CLOSED",
    }
