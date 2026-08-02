"""Evidence Management invariants (FR-EM-001 .. FR-EM-005)."""

from __future__ import annotations

import dataclasses

import pytest

from sanuvia.domain import (
    EvidenceClass,
    EvidenceRecord,
    InferenceRecord,
    InvariantViolation,
)
from tests.conftest import make_evidence, make_inference


def test_evidence_record_is_immutable() -> None:
    record = make_evidence()
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.content = "changed"  # type: ignore[misc]


def test_evidence_requires_non_empty_content() -> None:
    with pytest.raises(InvariantViolation):
        make_evidence(content="")


def test_all_six_evidence_classes_exist_including_failed_acquisition() -> None:
    names = {c.name for c in EvidenceClass}
    assert names == {
        "NARRATIVE",
        "REFLECTIVE",
        "BEHAVIOURAL",
        "CONTRADICTORY",
        "MISSING",
        "FAILED_ACQUISITION",
    }


def test_failed_acquisition_is_representable_as_evidence() -> None:
    # A failed acquisition is a first-class evidence-producing outcome, not an
    # exception path (FR-EM-004).
    record = make_evidence(
        evidence_class=EvidenceClass.FAILED_ACQUISITION,
        content="participant did not answer the reflection prompt",
    )
    assert record.evidence_class is EvidenceClass.FAILED_ACQUISITION


def test_evidence_and_inference_are_unrelated_types() -> None:
    # Structural guarantee of the never-conflate rule (FR-EM-005): neither is a
    # subclass of the other, so one can never stand in for the other.
    assert not issubclass(InferenceRecord, EvidenceRecord)
    assert not issubclass(EvidenceRecord, InferenceRecord)

    evidence = make_evidence()
    inference = make_inference()
    assert isinstance(evidence, EvidenceRecord)
    assert not isinstance(evidence, InferenceRecord)
    assert isinstance(inference, InferenceRecord)
    assert not isinstance(inference, EvidenceRecord)


def test_provenance_requires_source() -> None:
    from sanuvia.domain import Provenance, ProvenanceConfidence

    with pytest.raises(InvariantViolation):
        Provenance(source="", confidence=ProvenanceConfidence(0.5))
