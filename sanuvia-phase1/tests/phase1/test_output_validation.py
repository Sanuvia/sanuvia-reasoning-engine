"""Area 2 — strict output validation and the failure taxonomy.

Malformed model output at any of the four boundaries is rejected (not coerced into
empty evidence, empty hypotheses, default values, or fabricated confidence). A
failed call keeps its typed status; there are exactly six statuses.
"""

from __future__ import annotations

import json

import pytest

from sanuvia_phase1 import validation
from sanuvia_phase1.evidence_extractors import ExternalEvidenceExtractor
from sanuvia_phase1.failures import (
    BoundaryKind,
    CallStatus,
    MalformedOutputError,
    ModelError,
    ModelTimeout,
    RetryExhaustedError,
    classify_exception,
)
from sanuvia_phase1.transcript import TranscriptInteraction

# --- taxonomy -----------------------------------------------------------------


def test_call_status_has_exactly_the_six_defined_values() -> None:
    assert {s.value for s in CallStatus} == {
        "success",
        "malformed_output",
        "model_error",
        "timeout",
        "retry_exhausted",
        "configuration_error",
    }


def test_classify_exception_maps_each_family() -> None:
    assert classify_exception(
        MalformedOutputError(BoundaryKind.EVIDENCE_EXTRACTION, "x")
    ) == CallStatus.MALFORMED_OUTPUT
    assert classify_exception(ModelTimeout("slow")) == CallStatus.TIMEOUT
    assert classify_exception(ModelError("boom")) == CallStatus.MODEL_ERROR
    assert classify_exception(
        RetryExhaustedError(BoundaryKind.EVIDENCE_APPRAISAL, 3, CallStatus.MODEL_ERROR, "x")
    ) == CallStatus.RETRY_EXHAUSTED
    # An unexpected exception is a model error, never a success.
    assert classify_exception(RuntimeError("?")) == CallStatus.MODEL_ERROR


# --- A. evidence extraction ---------------------------------------------------


def _extract(raw: str) -> None:
    ExternalEvidenceExtractor(lambda _req: raw).extract(
        TranscriptInteraction(1, "seq-1", "some text"), "t"
    )


def test_extraction_missing_confidence_is_rejected_not_defaulted() -> None:
    raw = json.dumps(
        {"evidence": [{"observation": "said X", "evidence_class": "reflective"}]}
    )  # reliability / confidences absent — previously defaulted to 0.5
    with pytest.raises(MalformedOutputError):
        _extract(raw)


def test_extraction_out_of_range_confidence_is_rejected() -> None:
    raw = json.dumps(
        {
            "evidence": [
                {
                    "observation": "said X",
                    "evidence_class": "reflective",
                    "reliability": 1.5,
                    "classification_confidence": 0.5,
                    "provenance_confidence": 0.5,
                }
            ]
        }
    )
    with pytest.raises(MalformedOutputError):
        _extract(raw)


def test_extraction_unknown_class_and_non_object_are_rejected() -> None:
    with pytest.raises(MalformedOutputError):
        _extract(json.dumps({"evidence": [{"observation": "x", "evidence_class": "bogus",
                                           "reliability": 0.5, "classification_confidence": 0.5,
                                           "provenance_confidence": 0.5}]}))
    with pytest.raises(MalformedOutputError):
        _extract("not json at all")
    with pytest.raises(MalformedOutputError):
        _extract("[]")


def test_extraction_valid_output_passes() -> None:
    obs = validation.validate_extraction(
        json.dumps(
            {
                "evidence": [
                    {
                        "observation": "said X",
                        "evidence_class": "reflective",
                        "reliability": 0.7,
                        "classification_confidence": 0.8,
                        "provenance_confidence": 0.8,
                        "text_span": None,
                    }
                ]
            }
        )
    )
    assert len(obs) == 1 and obs[0].reliability == 0.7


# --- B. evidence appraisal ----------------------------------------------------


def test_appraisal_missing_statement_is_rejected() -> None:
    with pytest.raises(MalformedOutputError):
        validation.validate_appraisal(json.dumps({"proposals": [{"hypothesis_id": "H"}]}))


def test_appraisal_missing_or_out_of_range_support_is_rejected() -> None:
    with pytest.raises(MalformedOutputError):
        validation.validate_appraisal(
            json.dumps({"proposals": [{"hypothesis_id": "H", "statement": "s"}]})
        )
    with pytest.raises(MalformedOutputError):
        validation.validate_appraisal(
            json.dumps(
                {"proposals": [{"hypothesis_id": "H", "statement": "s", "initial_support": 9}]}
            )
        )


def test_appraisal_valid_output_passes() -> None:
    result = validation.validate_appraisal(
        json.dumps(
            {
                "supports": ["H1"],
                "contradicts": [],
                "proposals": [
                    {"hypothesis_id": "H2", "statement": "s", "initial_support": 0.4,
                     "supporting_evidence_ids": ["evidence-1"]}
                ],
            }
        )
    )
    assert result.supports == ("H1",)
    assert result.proposals[0].hypothesis_id == "H2"


# --- C/D. baseline conditions -------------------------------------------------


def test_baseline_absent_keys_are_empty_but_wrong_types_are_rejected() -> None:
    # absent keys => legitimately empty (documented, not a fallback for garbage)
    empty = validation.validate_baseline("{}", BoundaryKind.STATELESS_BASELINE)
    assert empty.best_explanations == ()
    assert empty.competing_hypotheses_held == ()
    # a held hypothesis missing its statement is malformed
    with pytest.raises(MalformedOutputError):
        validation.validate_baseline(
            json.dumps({"competing_hypotheses_held": [{"id": "H"}]}),
            BoundaryKind.TRANSCRIPT_BASELINE,
        )
    # best_explanations must be a list of strings
    with pytest.raises(MalformedOutputError):
        validation.validate_baseline(
            json.dumps({"best_explanations": "not-a-list"}),
            BoundaryKind.STATELESS_BASELINE,
        )
