"""Real evidence-extraction adapter — provider-neutral, injected client, no network;
plus real-mode end-to-end wiring with a fake client."""

from __future__ import annotations

import json

import pytest

from sanuvia.application.ports.reasoning import Appraisal, ProposedHypothesis
from sanuvia.domain import EvidenceRecordId, HypothesisId, SubjectId, shared_space_id

from sanuvia_phase1 import pipeline
from sanuvia_phase1.evidence_extractors import (
    ExternalEvidenceExtractor,
    ExtractionRequest,
    evidence_extractor_from_env,
)
from sanuvia_phase1.language_models import ScriptedLanguageModel
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction


def _fake_client(request: ExtractionRequest) -> str:
    """A deterministic in-process 'model' — no network. Echoes the turn text as a
    single observation."""
    return json.dumps(
        {
            "evidence": [
                {
                    "observation": request.transcript_text,
                    "evidence_class": "reflective",
                    "reliability": 0.7,
                    "classification_confidence": 0.8,
                    "provenance_confidence": 0.8,
                    "text_span": None,
                }
            ]
        }
    )


def test_external_extractor_parses_injected_client() -> None:
    extractor = ExternalEvidenceExtractor(_fake_client, extractor_id="fake-real")
    ti = TranscriptInteraction(1, "seq-1", "Person 1 said they feel stuck.")
    got = extractor.extract(ti, "t-real")
    assert len(got) == 1
    assert got[0].observation == "Person 1 said they feel stuck."
    assert got[0].evidence_class.value == "reflective"
    assert got[0].provenance.extractor_id == "fake-real"
    assert got[0].provenance.transcript_id == "t-real"


def test_external_extractor_hold_makes_no_client_call() -> None:
    calls: list[ExtractionRequest] = []

    def counting(request: ExtractionRequest) -> str:
        calls.append(request)
        return "{}"

    extractor = ExternalEvidenceExtractor(counting)
    assert extractor.extract(TranscriptInteraction(1, "seq-1", "   "), "t") == ()
    assert calls == []  # a hold consults no model


def test_from_env_refuses_to_autoselect_a_provider() -> None:
    with pytest.raises(RuntimeError):
        evidence_extractor_from_env()


def test_real_mode_end_to_end_wiring_with_fake_client() -> None:
    transcript = Transcript(
        "t-real",
        SubjectId("s-real"),
        shared_space_id("real"),
        (
            TranscriptInteraction(1, "seq-1", "Person 1 said they feel stuck."),
            TranscriptInteraction(2, "seq-2", "Person 1 said they want to build something new."),
        ),
    )
    # Appraisal (evidence -> hypotheses) stays a Phase 0 concern; here a scripted
    # appraisal keyed by the first extracted evidence proposes a hypothesis.
    appraisal = {
        EvidenceRecordId("evidence-1"): Appraisal(
            proposals=(ProposedHypothesis(HypothesisId("H_x"), "H_x: a candidate reading.", 0.4, ()),)
        )
    }
    tdr = pipeline.run_transcript_demonstration(
        transcript,
        ExternalEvidenceExtractor(_fake_client, extractor_id="fake-real"),
        appraisal,
        {"H_x": "H_x: a candidate reading."},
        ScriptedLanguageModel(("{}", "{}")),
        ScriptedLanguageModel(("{}", "{}")),
        case_id="real-wiring",
        mode=pipeline.REAL,
    )
    assert tdr.mode == "real"
    assert tdr.extractor_id == "fake-real"
    sanuvia = tdr.demonstration.records_by_condition["sanuvia_persistent"]
    # Real extraction fed the frozen engine, which formed the hypothesis.
    assert any(h.hypothesis_id == "H_x" for h in sanuvia[0].hypotheses)
