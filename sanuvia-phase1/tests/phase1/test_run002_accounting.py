"""Run 002 amendment — failure/interaction accounting (Gate 2).

Proves, with SYNTHETIC inputs and no model (Case 001 is never used):
  * a malformed response validated *inside* the recorded boundary is recorded as
    MALFORMED_OUTPUT (not SUCCESS), with the backend text preserved in raw_response
    (distinguishing backend-returned text from the validated-boundary outcome);
  * an early abort leaves later interactions explicitly NOT_EXECUTED, never SUCCESS;
  * NOT_EXECUTED is an interaction-level status, not a CallStatus.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from sanuvia.domain import SubjectId, shared_space_id

from sanuvia_phase1.failures import (
    BoundaryKind,
    CallStatus,
    InteractionStatus,
    MalformedOutputError,
)
from sanuvia_phase1.manifest import RunManifestBuilder, call_with_recording
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction
from sanuvia_phase1.validation import validate_extraction

# --- synthetic (non-Case-001) transcript -------------------------------------


def _transcript(seqs: tuple[str, ...]) -> Transcript:
    return Transcript(
        "synthetic-run002",
        SubjectId("s-synth"),
        shared_space_id("synth"),
        tuple(TranscriptInteraction(i + 1, s, f"synthetic text {i+1}") for i, s in enumerate(seqs)),
    )


def _builder(seqs: tuple[str, ...]) -> RunManifestBuilder:
    return RunManifestBuilder(
        run_id="r002", created_at="2026-01-01T00:00:00Z", git_commit_sha="sha",
        phase1_version="0.1.0", mode="real", transcript=_transcript(seqs),
    )


def _validating_thunk(raw: str, validator: Callable[[str], object]) -> Callable[[], str]:
    """Mimics the local validating-recording wiring: the recorded boundary both
    generates (returns raw) AND validates, so a schema failure raises inside the
    recorded thunk and is accounted at the boundary."""
    def thunk() -> str:
        validator(raw)  # raises MalformedOutputError on malformed output
        return raw
    return thunk


# NB: the exact envelope that broke Run 001 — <think>… then JSON.
_MALFORMED = (
    '<think>\nreasoning…\n</think>\n\n'
    '{"evidence": [{"observation": "x", "evidence_class": "narrative", '
    '"reliability": 1.0, "classification_confidence": 1.0, '
    '"provenance_confidence": 1.0, "text_span": null}]}'
)
_VALID = (
    '{"evidence": [{"observation": "x", "evidence_class": "narrative", '
    '"reliability": 1.0, "classification_confidence": 1.0, '
    '"provenance_confidence": 1.0, "text_span": null}]}'
)


def test_malformed_validated_at_boundary_is_recorded_malformed_not_success() -> None:
    builder = _builder(("seq-1", "seq-2"))
    with pytest.raises(MalformedOutputError):
        call_with_recording(
            builder,
            boundary=BoundaryKind.EVIDENCE_EXTRACTION,
            interaction_index=1,
            seq_label="seq-1",
            model_role="evidence_extraction",
            thunk=_validating_thunk(_MALFORMED, validate_extraction),
            retries=0,
        )
    manifest = builder.finalize()
    rec = manifest.call_records[0]
    # boundary outcome (status) is MALFORMED, NOT success…
    assert rec.status == CallStatus.MALFORMED_OUTPUT.value
    # …while the backend-returned text is preserved verbatim in raw_response
    assert rec.raw_response == _MALFORMED
    assert rec.attempts == 1  # retries=0 -> not retried


def test_valid_output_at_boundary_is_success_with_raw_preserved() -> None:
    builder = _builder(("seq-1",))
    raw = call_with_recording(
        builder,
        boundary=BoundaryKind.EVIDENCE_EXTRACTION,
        interaction_index=1,
        seq_label="seq-1",
        model_role="evidence_extraction",
        thunk=_validating_thunk(_VALID, validate_extraction),
        retries=0,
    )
    assert raw == _VALID
    rec = builder.finalize().call_records[0]
    assert rec.status == CallStatus.SUCCESS.value
    assert rec.raw_response == _VALID


def test_early_abort_leaves_later_interactions_not_executed() -> None:
    # Simulate an abort at seq-1 (the only attempted interaction).
    builder = _builder(("seq-1", "seq-2", "seq-3"))
    with pytest.raises(MalformedOutputError):
        call_with_recording(
            builder,
            boundary=BoundaryKind.EVIDENCE_EXTRACTION,
            interaction_index=1,
            seq_label="seq-1",
            model_role="evidence_extraction",
            thunk=_validating_thunk(_MALFORMED, validate_extraction),
            retries=0,
        )
    status = dict(builder.finalize().per_interaction_status)
    assert status["seq-1"] == CallStatus.MALFORMED_OUTPUT.value
    assert status["seq-2"] == InteractionStatus.NOT_EXECUTED.value
    assert status["seq-3"] == InteractionStatus.NOT_EXECUTED.value
    # crucially: never SUCCESS for the un-attempted interactions
    assert status["seq-2"] != CallStatus.SUCCESS.value
    assert status["seq-3"] != CallStatus.SUCCESS.value


def test_mark_started_without_a_call_is_success_not_not_executed() -> None:
    # An interaction whose processing began but issued no model call (e.g. a hold)
    # is SUCCESS; one never begun is NOT_EXECUTED.
    builder = _builder(("seq-1", "seq-2"))
    builder.mark_started("seq-1")
    status = dict(builder.finalize().per_interaction_status)
    assert status["seq-1"] == InteractionStatus.SUCCESS.value
    assert status["seq-2"] == InteractionStatus.NOT_EXECUTED.value


def test_not_executed_is_interaction_level_not_a_callstatus() -> None:
    assert "not_executed" not in {s.value for s in CallStatus}
    assert InteractionStatus.NOT_EXECUTED.value == "not_executed"
