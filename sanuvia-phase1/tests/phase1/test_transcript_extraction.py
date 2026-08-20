"""Transcript input parsing, deterministic extraction, provenance, and the
evidence-vs-inference boundary."""

from __future__ import annotations

from fixtures.longitudinal.case_001 import CASE_001
from fixtures.longitudinal.case_001_transcript import (
    CASE_001_TRANSCRIPT,
    case_001_scripted_extractor,
)

from sanuvia_phase1.extraction import ExtractedEvidence


def test_transcript_preserves_longitudinal_order_and_holds() -> None:
    t = CASE_001_TRANSCRIPT
    assert [i.seq_label for i in t.interactions] == [
        "seq-1", "seq-2", "seq-3", "seq-4", "seq-5", "seq-6"
    ]
    assert t.interactions[4].text == ""  # seq-5 is a genuine hold


def test_deterministic_extraction_is_repeatable_and_provenanced() -> None:
    extractor = case_001_scripted_extractor()
    a = extractor.extract(CASE_001_TRANSCRIPT.interactions[0], CASE_001_TRANSCRIPT.transcript_id)
    b = extractor.extract(CASE_001_TRANSCRIPT.interactions[0], CASE_001_TRANSCRIPT.transcript_id)
    assert a == b  # deterministic
    e = a[0]
    assert isinstance(e, ExtractedEvidence)
    assert e.provenance.transcript_id == CASE_001_TRANSCRIPT.transcript_id
    assert e.provenance.source_interaction_index == 1
    assert e.provenance.seq_label == "seq-1"
    assert e.provenance.extractor_id == "case-001-golden-extractor"
    assert e.provenance.extraction_status == "extracted"


def test_hold_extracts_no_evidence() -> None:
    extractor = case_001_scripted_extractor()
    got = extractor.extract(CASE_001_TRANSCRIPT.interactions[4], CASE_001_TRANSCRIPT.transcript_id)
    assert got == ()


def test_extraction_is_observation_not_inference() -> None:
    # Extracted observations equal the authored RawObservations — the extractor
    # injects no interpretation, and the DTO has no hypothesis/inference field.
    extractor = case_001_scripted_extractor()
    for ti, ci in zip(CASE_001_TRANSCRIPT.interactions, CASE_001.interactions, strict=True):
        extracted = extractor.extract(ti, CASE_001_TRANSCRIPT.transcript_id)
        assert tuple(e.observation for e in extracted) == tuple(ce.text for ce in ci.evidence)
    fields = ExtractedEvidence.__dataclass_fields__
    assert "hypothesis" not in fields
    assert "inference" not in fields
