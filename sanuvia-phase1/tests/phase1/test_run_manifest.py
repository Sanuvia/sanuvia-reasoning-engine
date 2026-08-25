"""Area 3 — immutable, auditable run manifest.

Captures identity, the full transcript, model specs, raw responses, retries, and
per-interaction status; is immutable after finalize; serializes deterministically;
stores no secrets; and records provider-unavailable fields honestly (distinguishing
"not provided by provider" from "not captured").
"""

from __future__ import annotations

import json

import pytest

from fixtures.offline_real import offline_real_config

from sanuvia.domain import SubjectId, shared_space_id

from sanuvia_phase1.failures import (
    Availability,
    BoundaryKind,
    CallStatus,
    Maybe,
    MalformedOutputError,
    ModelError,
    ModelTimeout,
    Phase1Error,
    RetryExhaustedError,
)
from sanuvia_phase1.manifest import RunManifestBuilder, call_with_recording
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction


def _transcript() -> Transcript:
    return Transcript(
        "t-manifest",
        SubjectId("s"),
        shared_space_id("x"),
        (
            TranscriptInteraction(1, "seq-1", "turn one"),
            TranscriptInteraction(2, "seq-2", "turn two"),
        ),
    )


def _builder(**overrides: object) -> RunManifestBuilder:
    kwargs: dict[str, object] = dict(
        run_id="run-001",
        created_at="2026-01-01T00:00:00Z",
        git_commit_sha="deadbeef",
        phase1_version="0.1.0",
        mode="real",
        transcript=_transcript(),
        model_specs=offline_real_config().specs(),
        notes="test",
    )
    kwargs.update(overrides)
    return RunManifestBuilder(**kwargs)  # type: ignore[arg-type]


def test_manifest_is_immutable_after_finalize() -> None:
    builder = _builder()
    manifest = builder.finalize()
    # frozen dataclass: fields cannot be reassigned
    with pytest.raises(Exception):
        manifest.run_id = "changed"  # type: ignore[misc]
    # builder rejects further records and a second finalize
    with pytest.raises(Phase1Error):
        call_with_recording(
            builder,
            boundary=BoundaryKind.STATELESS_BASELINE,
            interaction_index=1,
            seq_label="seq-1",
            model_role="stateless_baseline",
            thunk=lambda: "{}",
        )
    with pytest.raises(Phase1Error):
        builder.finalize()


def test_deterministic_serialization() -> None:
    a = _builder().finalize().to_json()
    b = _builder().finalize().to_json()
    assert a == b
    # canonical (sorted keys) so it is reproducible where inputs are
    assert json.loads(a)["run_id"] == "run-001"


def test_records_success_and_captures_raw_response() -> None:
    builder = _builder()
    raw = call_with_recording(
        builder,
        boundary=BoundaryKind.EVIDENCE_EXTRACTION,
        interaction_index=1,
        seq_label="seq-1",
        model_role="evidence_extraction",
        thunk=lambda: '{"evidence": []}',
    )
    assert raw == '{"evidence": []}'
    manifest = builder.finalize()
    rec = manifest.call_records[0]
    assert rec.status == CallStatus.SUCCESS.value
    assert rec.raw_response == '{"evidence": []}'
    assert rec.attempts == 1


def test_malformed_output_is_recorded_and_not_retried() -> None:
    builder = _builder()

    def bad() -> str:
        raise MalformedOutputError(BoundaryKind.EVIDENCE_EXTRACTION, "bad schema", raw="garbage")

    with pytest.raises(MalformedOutputError):
        call_with_recording(
            builder,
            boundary=BoundaryKind.EVIDENCE_EXTRACTION,
            interaction_index=1,
            seq_label="seq-1",
            model_role="evidence_extraction",
            thunk=bad,
            retries=3,  # malformed output must NOT be retried
        )
    manifest = builder.finalize()
    rec = manifest.call_records[0]
    assert rec.status == CallStatus.MALFORMED_OUTPUT.value
    assert rec.attempts == 1
    assert rec.raw_response == "garbage"
    # per-interaction status reflects the failure
    assert ("seq-1", CallStatus.MALFORMED_OUTPUT.value) in manifest.per_interaction_status
    assert ("seq-2", CallStatus.SUCCESS.value) in manifest.per_interaction_status


def test_model_error_retries_then_exhausts() -> None:
    builder = _builder()
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        raise ModelTimeout("slow")

    with pytest.raises(RetryExhaustedError):
        call_with_recording(
            builder,
            boundary=BoundaryKind.TRANSCRIPT_BASELINE,
            interaction_index=2,
            seq_label="seq-2",
            model_role="transcript_baseline",
            thunk=flaky,
            retries=2,
        )
    assert calls["n"] == 3  # initial + 2 retries
    rec = builder.finalize().call_records[0]
    assert rec.status == CallStatus.RETRY_EXHAUSTED.value
    assert rec.attempts == 3


def test_model_error_without_retries_propagates_as_model_error() -> None:
    builder = _builder()

    def boom() -> str:
        raise ModelError("provider exploded")

    with pytest.raises(ModelError):
        call_with_recording(
            builder,
            boundary=BoundaryKind.EVIDENCE_APPRAISAL,
            interaction_index=1,
            seq_label="seq-1",
            model_role="evidence_appraisal",
            thunk=boom,
        )
    rec = builder.finalize().call_records[0]
    assert rec.status == CallStatus.MODEL_ERROR.value


def test_availability_tri_state_is_honest() -> None:
    spec = offline_real_config().extraction
    assert spec.seed.availability == Availability.AVAILABLE
    assert spec.seed.value == "0"
    assert spec.model_version.availability == Availability.NOT_PROVIDED_BY_PROVIDER
    assert spec.model_version.value is None
    # a not-captured field is distinct from not-provided
    assert Maybe.not_captured().availability == Availability.NOT_CAPTURED


def test_manifest_stores_no_secrets() -> None:
    builder = _builder()
    call_with_recording(
        builder,
        boundary=BoundaryKind.STATELESS_BASELINE,
        interaction_index=1,
        seq_label="seq-1",
        model_role="stateless_baseline",
        thunk=lambda: "{}",
        session_id=Maybe.available("sess-abc"),
    )
    blob = builder.finalize().to_json().lower()
    # Credential-specific markers (note: "max_output_tokens" is a legitimate
    # parameter, so we do not scan for the bare substring "token").
    for secret in (
        "api_key", "apikey", "secret", "authorization", "bearer ",
        "password", "credential", "access_key", "client_secret",
    ):
        assert secret not in blob
