"""Real evidence-appraiser adapter — provider-neutral, injected client, no network.
Proves the LLM only PROPOSES; the frozen Phase 0 engine owns revision/persistence.
"""

from __future__ import annotations

import json

import pytest

from sanuvia.domain import SubjectId, shared_space_id

from sanuvia_phase1 import pipeline
from sanuvia_phase1.evidence_appraisers import (
    AppraisalRequest,
    ExternalEvidenceAppraiser,
    evidence_appraiser_from_env,
)
from sanuvia_phase1.evidence_extractors import ExternalEvidenceExtractor, ExtractionRequest
from sanuvia_phase1.language_models import ScriptedLanguageModel
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction


def _extract_client(request: ExtractionRequest) -> str:
    """Fake extractor: echoes the turn as one observation. No network."""
    return json.dumps(
        {
            "evidence": [
                {
                    "observation": request.transcript_text,
                    "evidence_class": "reflective",
                    "reliability": 0.8,
                    "classification_confidence": 0.9,
                    "provenance_confidence": 0.9,
                    "text_span": None,
                }
            ]
        }
    )


def _appraise_client(request: AppraisalRequest) -> str:
    """Fake appraiser: proposes H_real for the 'stuck' observation, else nothing."""
    if "stuck" in request.evidence_observation:
        return json.dumps(
            {
                "proposals": [
                    {
                        "hypothesis_id": "H_real",
                        "statement": "H_real: a candidate reading proposed by the appraiser.",
                        "initial_support": 0.4,
                        "supporting_evidence_ids": [],
                    }
                ]
            }
        )
    return "{}"


def _transcript() -> Transcript:
    return Transcript(
        "t-appraise",
        SubjectId("s-appraise"),
        shared_space_id("appraise"),
        (
            TranscriptInteraction(1, "seq-1", "Person 1 said they feel stuck."),
            TranscriptInteraction(2, "seq-2", "Person 1 said they want to build something new."),
        ),
    )


def test_from_env_refuses_to_autoselect_a_provider() -> None:
    with pytest.raises(RuntimeError):
        evidence_appraiser_from_env()


def test_real_appraiser_end_to_end_forms_hypothesis_via_frozen_engine() -> None:
    tdr = pipeline.run_transcript_demonstration(
        _transcript(),
        ExternalEvidenceExtractor(_extract_client, extractor_id="fake-real"),
        {},   # appraisal_script unused: a real appraiser is injected
        {},   # hypothesis_catalogue not needed for a real appraiser
        ScriptedLanguageModel(("{}", "{}")),
        ScriptedLanguageModel(("{}", "{}")),
        case_id="real-appraise",
        mode=pipeline.REAL,
        appraiser=ExternalEvidenceAppraiser(_appraise_client),
    )
    assert tdr.mode == "real"
    sanuvia = tdr.demonstration.records_by_condition["sanuvia_persistent"]
    # The appraiser PROPOSED H_real; the FROZEN ENGINE performed the revision and
    # assigned the model version — the boundary is respected.
    assert any(h.hypothesis_id == "H_real" for h in sanuvia[0].hypotheses)
    assert sanuvia[0].model_version_id == "wm-1"
    assert [e.outcome for e in sanuvia[0].revision_events] == ["hypothesize"]
    assert sanuvia[0].revision_events[0].affected_object_id == "H_real"


def test_malformed_proposal_is_skipped() -> None:
    def bad_appraise(request: AppraisalRequest) -> str:
        # a proposal missing 'statement' must be skipped (not crash, not invent)
        return json.dumps({"proposals": [{"hypothesis_id": "H_bad"}]})

    tdr = pipeline.run_transcript_demonstration(
        _transcript(),
        ExternalEvidenceExtractor(_extract_client),
        {},
        {},
        ScriptedLanguageModel(("{}", "{}")),
        ScriptedLanguageModel(("{}", "{}")),
        case_id="real-appraise-bad",
        mode=pipeline.REAL,
        appraiser=ExternalEvidenceAppraiser(bad_appraise),
    )
    sanuvia = tdr.demonstration.records_by_condition["sanuvia_persistent"]
    assert all(h.hypothesis_id != "H_bad" for h in sanuvia[0].hypotheses)


def test_golden_mode_unaffected_when_no_appraiser_injected() -> None:
    # Passing appraiser=None must preserve the scripted-appraiser golden behavior.
    from fixtures.longitudinal.case_001 import CASE_001
    from sanuvia_phase1.conditions import SanuviaPersistentCondition

    a = SanuviaPersistentCondition(CASE_001)  # default (None)
    a.start()
    default_records = [a.step(i) for i in CASE_001.interactions]
    b = SanuviaPersistentCondition(CASE_001, appraiser=None)  # explicit None
    b.start()
    explicit_records = [b.step(i) for i in CASE_001.interactions]
    assert default_records == explicit_records
