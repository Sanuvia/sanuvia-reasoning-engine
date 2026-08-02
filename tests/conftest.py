"""Shared test builders for constructing valid domain objects concisely.

These helpers produce *valid* instances with sensible defaults so each test can
override just the field under scrutiny. They live in the test tree only.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sanuvia.domain import (
    EvidenceClass,
    EvidenceRecord,
    EvidenceRecordId,
    EvidenceReliability,
    ClassificationConfidence,
    Hypothesis,
    HypothesisId,
    HypothesisRecordId,
    InferenceRecord,
    InferenceRecordId,
    Provenance,
    ProvenanceConfidence,
    SubjectId,
    WorldModelVersionId,
)

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

SUBJECT = SubjectId("subject-1")


def make_provenance(confidence: float = 0.9) -> Provenance:
    return Provenance(
        source="reflection:session-1",
        confidence=ProvenanceConfidence(confidence),
        acquisition_metadata=(("channel", "written"),),
    )


def make_evidence(
    *,
    evidence_id: str = "ev-1",
    evidence_class: EvidenceClass = EvidenceClass.BEHAVIOURAL,
    content: str = "partner arrived home later than usual",
    reliability: float = 0.7,
    classification_confidence: float = 0.8,
    occurred_at: datetime = T0,
) -> EvidenceRecord:
    return EvidenceRecord(
        id=EvidenceRecordId(evidence_id),
        subject_id=SUBJECT,
        evidence_class=evidence_class,
        content=content,
        provenance=make_provenance(),
        reliability=EvidenceReliability(reliability),
        classification_confidence=ClassificationConfidence(classification_confidence),
        occurred_at=occurred_at,
    )


def make_inference(*, inference_id: str = "inf-1") -> InferenceRecord:
    return InferenceRecord(
        id=InferenceRecordId(inference_id),
        subject_id=SUBJECT,
        content="partner may be emotionally distant",
        derived_from_evidence_ids=(EvidenceRecordId("ev-1"),),
        derived_from_inference_ids=(),
        produced_at=T0,
    )


def make_hypothesis(
    *,
    record_id: str = "hyp-rec-1",
    hypothesis_id: str = "hyp-1",
    support: float = 0.5,
    supporting: tuple[str, ...] = ("ev-1",),
    contradicting: tuple[str, ...] = (),
) -> Hypothesis:
    from sanuvia.domain import HypothesisSupport

    return Hypothesis(
        record_id=HypothesisRecordId(record_id),
        hypothesis_id=HypothesisId(hypothesis_id),
        statement="increasing emotional distance",
        support=HypothesisSupport(support),
        supporting_evidence_ids=tuple(EvidenceRecordId(e) for e in supporting),
        contradicting_evidence_ids=tuple(EvidenceRecordId(e) for e in contradicting),
        evaluated_at_version=WorldModelVersionId("wm-1"),
        evaluated_at=T0,
    )
