"""Real evidence-extraction adapter — provider-neutral, injected client, no network;
plus real-mode end-to-end wiring with a fake client."""

from __future__ import annotations

import json

import pytest

from fixtures.offline_real import offline_real_config

from sanuvia.domain import SubjectId, shared_space_id

from sanuvia_phase1 import pipeline
from sanuvia_phase1.evidence_appraisers import AppraisalRequest, ExternalEvidenceAppraiser
from sanuvia_phase1.evidence_extractors import (
    ExternalEvidenceExtractor,
    ExtractionRequest,
    evidence_extractor_from_env,
)
from sanuvia_phase1.language_models import ExternalLanguageModel
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


def _appraise_client(request: AppraisalRequest) -> str:
    """Offline fake appraiser: proposes H_x for the 'stuck' observation."""
    if "stuck" in request.evidence_observation:
        return json.dumps(
            {
                "proposals": [
                    {
                        "hypothesis_id": "H_x",
                        "statement": "H_x: a candidate reading.",
                        "initial_support": 0.4,
                        "supporting_evidence_ids": [],
                    }
                ]
            }
        )
    return "{}"


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
    # REAL mode: real adapters (offline fake clients) for every boundary + explicit
    # config. Appraisal is a real EvidenceAppraiser — REAL never uses a scripted
    # appraisal script. The frozen engine still forms the hypothesis.
    tdr = pipeline.run_transcript_demonstration(
        transcript,
        ExternalEvidenceExtractor(_fake_client, extractor_id="fake-real"),
        {},
        {},
        ExternalLanguageModel(lambda _req: "{}"),
        ExternalLanguageModel(lambda _req: "{}"),
        case_id="real-wiring",
        mode=pipeline.REAL,
        appraiser=ExternalEvidenceAppraiser(_appraise_client),
        config=offline_real_config(),
    )
    assert tdr.mode == "real"
    assert tdr.extractor_id == "fake-real"
    sanuvia = tdr.demonstration.records_by_condition["sanuvia_persistent"]
    # Real extraction + real appraisal fed the frozen engine, which formed the hypothesis.
    assert any(h.hypothesis_id == "H_x" for h in sanuvia[0].hypotheses)
