"""Real evidence-appraiser adapter — provider-neutral, injected client, no network.
Proves the LLM only PROPOSES; the frozen Phase 0 engine owns revision/persistence.

REAL mode uses only non-scripted components (real adapters wrapping offline fake
clients) plus an explicit offline ``RealRunConfig`` — it never falls back to a
scripted double.
"""

from __future__ import annotations

import json

import pytest

from fixtures.offline_real import offline_real_config

from sanuvia.domain import SubjectId, shared_space_id

from sanuvia_phase1 import pipeline
from sanuvia_phase1.evidence_appraisers import (
    AppraisalPrompt,
    ExternalEvidenceAppraiser,
    evidence_appraiser_from_env,
)
from sanuvia_phase1.evidence_extractors import ExternalEvidenceExtractor, ExtractionRequest
from sanuvia_phase1.failures import MalformedOutputError
from sanuvia_phase1.language_models import ExternalLanguageModel
from sanuvia_phase1.ports import LmRequest
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


def _appraise_client(request: AppraisalPrompt) -> str:
    """Fake appraiser: proposes H_real for the 'stuck' observation, else nothing."""
    if "stuck" in request.evidence_observation:
        return json.dumps(
            {
                "proposals": [
                    {
                        "local_ref": "p1",
                        "statement": "H_real: a candidate reading proposed by the appraiser.",
                    }
                ]
            }
        )
    return "{}"


def _empty_baseline(_request: LmRequest) -> str:
    """A fake, offline baseline client returning a well-formed empty answer."""
    return "{}"


def _baselines() -> tuple[ExternalLanguageModel, ExternalLanguageModel]:
    return ExternalLanguageModel(_empty_baseline), ExternalLanguageModel(_empty_baseline)


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
    stateless, transcript_model = _baselines()
    tdr = pipeline.run_transcript_demonstration(
        _transcript(),
        ExternalEvidenceExtractor(_extract_client, extractor_id="fake-real"),
        {},   # appraisal_script unused: a real appraiser is injected
        {},   # hypothesis_catalogue not needed for a real appraiser
        stateless,
        transcript_model,
        case_id="real-appraise",
        mode=pipeline.REAL,
        appraiser=ExternalEvidenceAppraiser(_appraise_client),
        config=offline_real_config(),
    )
    assert tdr.mode == "real"
    sanuvia = tdr.demonstration.records_by_condition["sanuvia_persistent"]
    # The appraiser PROPOSED a reading; the FROZEN ENGINE performed the revision,
    # assigned the model version AND issued the durable identity. Under Technical
    # Design v1.5.4 the boundary is stronger than it was: locked §3.3 gives the
    # engine every durable hypothesis id, so the appraiser's "H_real" must NOT
    # survive into reasoning state.
    (hypothesis,) = sanuvia[0].hypotheses
    assert hypothesis.hypothesis_id != "p1", (
        "a model-authored id must never become durable identity"
    )
    assert hypothesis.statement == (
        "H_real: a candidate reading proposed by the appraiser."
    ), "the proposed language is kept; only the identity is the engine's"
    assert sanuvia[0].model_version_id == "wm-1"
    assert [e.outcome for e in sanuvia[0].revision_events] == ["hypothesize"]
    assert sanuvia[0].revision_events[0].affected_object_id == hypothesis.hypothesis_id


def test_malformed_proposal_is_rejected_not_silently_skipped() -> None:
    # HARDENED: a proposal missing 'statement' is malformed output. It must be
    # rejected (MalformedOutputError), never silently skipped or defaulted.
    def bad_appraise(_request: AppraisalPrompt) -> str:
        return json.dumps({"proposals": [{"local_ref": "p_bad"}]})

    stateless, transcript_model = _baselines()
    with pytest.raises(MalformedOutputError):
        pipeline.run_transcript_demonstration(
            _transcript(),
            ExternalEvidenceExtractor(_extract_client),
            {},
            {},
            stateless,
            transcript_model,
            case_id="real-appraise-bad",
            mode=pipeline.REAL,
            appraiser=ExternalEvidenceAppraiser(bad_appraise),
            config=offline_real_config(),
        )


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
