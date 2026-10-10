"""Case 001 transcript → deterministic extraction → Phase 0, and its equivalence
to the existing structured-evidence path; FM baselines read raw text."""

from __future__ import annotations

from fixtures.longitudinal.case_001_baseline_scripts import deterministic_language_models
from fixtures.longitudinal.case_001 import CASE_001
from fixtures.longitudinal.case_001_transcript import (
    CASE_001_APPRAISAL_SCRIPT,
    CASE_001_HYPOTHESIS_CATALOGUE,
    CASE_001_TRANSCRIPT,
    case_001_scripted_extractor,
)

from sanuvia_phase1 import pipeline, report
from sanuvia_phase1.conditions import SanuviaPersistentCondition
from sanuvia_phase1.pipeline import TranscriptDemonstrationReport


def _transcript_report() -> TranscriptDemonstrationReport:
    stateless, transcript = deterministic_language_models()
    return pipeline.run_transcript_demonstration(
        CASE_001_TRANSCRIPT,
        case_001_scripted_extractor(),
        CASE_001_APPRAISAL_SCRIPT,
        CASE_001_HYPOTHESIS_CATALOGUE,
        stateless,
        transcript,
        case_id="case-001-transcript",
        mode=pipeline.GOLDEN,
    )


def test_transcript_sanuvia_trajectory_equals_structured_path() -> None:
    condition = SanuviaPersistentCondition(CASE_001)
    condition.start()
    structured = tuple(condition.step(i) for i in CASE_001.interactions)
    condition.finish()

    tdr = _transcript_report()
    # Same reasoning trajectory whether evidence is authored directly or extracted
    # from the transcript by the deterministic golden extractor.
    assert tdr.demonstration.records_by_condition["sanuvia_persistent"] == structured


def test_fm_baselines_read_raw_text_not_structured_evidence() -> None:
    tdr = _transcript_report()
    sanuvia = tdr.demonstration.records_by_condition["sanuvia_persistent"]
    stateless = tdr.demonstration.records_by_condition["fm_stateless"]
    # Sanuvia ingests extracted structured evidence (ER refs); the FM baseline
    # ingests the raw conversation turn.
    assert sanuvia[0].ingested_evidence_ids == ("ER-001",)
    assert stateless[0].ingested_evidence_ids == ("turn-1",)
    # All three conditions share the same ordered interaction sequence.
    seq = [i.seq_label for i in CASE_001_TRANSCRIPT.interactions]
    for recs in tdr.demonstration.records_by_condition.values():
        assert [r.seq_label for r in recs] == seq


def test_transcript_run_is_byte_identical_and_mode_tagged() -> None:
    first = report.transcript_to_json(_transcript_report())
    second = report.transcript_to_json(_transcript_report())
    assert first == second
    assert '"mode": "golden"' in first
    assert '"extractor_id": "case-001-golden-extractor"' in first
