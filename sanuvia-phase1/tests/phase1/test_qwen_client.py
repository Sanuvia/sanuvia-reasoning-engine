"""Local Qwen client boundary — configuration, generation, metadata capture,
error/timeout classification, retry recording, deterministic params. All offline
via an injected fake backend (no network, no vendor SDK, no download)."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from sanuvia_phase1 import prompts
from sanuvia_phase1.evidence_appraisers.external import AppraisalRequest
from sanuvia_phase1.evidence_extractors.external import ExtractionRequest
from sanuvia_phase1.failures import (
    Availability,
    BoundaryKind,
    CallStatus,
    Maybe,
    ModelError,
    ModelTimeout,
    RetryExhaustedError,
)
from sanuvia_phase1.manifest import RunManifestBuilder
from sanuvia_phase1.ports import LmRequest
from sanuvia_phase1.qwen import (
    PROVIDER,
    QWEN3_4B,
    GenerationParams,
    QwenClient,
    QwenRuntimeInfo,
    _normalise_llama_cpp_build,
    detect_local_qwen,
    qwen_real_run_config,
)
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction


class FakeBackend:
    """An injected, in-process backend — no network, no model download."""

    def __init__(
        self,
        responder: Callable[[str], str] | None = None,
        *,
        raise_exc: Exception | None = None,
    ) -> None:
        self.calls: list[tuple[str, GenerationParams]] = []
        self._responder = responder
        self._raise = raise_exc

    def describe(self) -> QwenRuntimeInfo:
        return QwenRuntimeInfo(
            backend_id="fake-offline",
            model_id="qwen3-4b",
            model_version=Maybe.available("fake-2024.1"),
            artifact_id=Maybe.available("/models/fake-qwen3-4b.gguf"),
            context_window=8192,
        )

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self.calls.append((prompt, params))
        if self._raise is not None:
            raise self._raise
        return self._responder(prompt) if self._responder else "{}"


def _transcript() -> Transcript:
    from sanuvia.domain import SubjectId, shared_space_id

    return Transcript(
        "t", SubjectId("s"), shared_space_id("x"),
        (TranscriptInteraction(1, "seq-1", "one"),),
    )


def _builder(backend_specs: bool = True) -> RunManifestBuilder:
    return RunManifestBuilder(
        run_id="r", created_at="2026-01-01T00:00:00Z", git_commit_sha="sha",
        phase1_version="0.1.0", mode="real", transcript=_transcript(),
        model_specs=qwen_real_run_config().specs() if backend_specs else (),
    )


def _params(seed: int | None = 0) -> GenerationParams:
    return GenerationParams(temperature=0.0, max_output_tokens=128, context_tokens=4096, seed=seed)


def test_config_is_complete_and_local() -> None:
    cfg = qwen_real_run_config()
    assert cfg._incomplete() == []
    for spec in cfg.specs():
        assert spec.provider == PROVIDER == "local_qwen"
        assert spec.prompt_id in prompts.PROMPTS
        assert spec.schema_id in prompts.SCHEMAS
        assert spec.temperature == 0.0
        assert spec.seed.availability == Availability.AVAILABLE and spec.seed.value == "0"
    # candidate model documented, not silently chosen
    assert cfg.extraction.model == QWEN3_4B.model_id == "qwen3-4b"
    # exact version/artifact are honestly "not captured" until a runtime provides them
    assert cfg.extraction.model_version.availability == Availability.NOT_CAPTURED


def test_baselines_share_prompt_and_schema_ids() -> None:
    cfg = qwen_real_run_config()
    assert cfg.stateless_baseline.prompt_id == cfg.transcript_baseline.prompt_id
    assert cfg.stateless_baseline.schema_id == cfg.transcript_baseline.schema_id


def test_extraction_call_is_recorded_with_raw_and_params() -> None:
    backend = FakeBackend(lambda _p: '{"evidence": []}')
    builder = _builder()
    client = QwenClient(backend, _params(seed=0), builder)
    client.begin_interaction(1, "seq-1")
    raw = client.extraction_client()(
        ExtractionRequest(system="S", transcript_text="hello", instruction="I")
    )
    assert raw == '{"evidence": []}'
    # deterministic params reached the backend
    assert backend.calls[0][1].seed == 0
    assert backend.calls[0][1].temperature == 0.0
    rec = builder.finalize().call_records[0]
    assert rec.boundary == BoundaryKind.EVIDENCE_EXTRACTION.value
    assert rec.status == CallStatus.SUCCESS.value
    assert rec.seq_label == "seq-1"
    assert rec.raw_response == '{"evidence": []}'
    # a local model has no server session/cache — recorded honestly, not invented
    assert rec.session_id.availability == Availability.NOT_PROVIDED_BY_PROVIDER


def test_timeout_is_classified_and_recorded() -> None:
    backend = FakeBackend(raise_exc=ModelTimeout("too slow"))
    builder = _builder()
    client = QwenClient(backend, _params(), builder)
    client.begin_interaction(2, "seq-2")
    with pytest.raises(ModelTimeout):
        client.baseline_client(BoundaryKind.STATELESS_BASELINE, "stateless_baseline")(
            LmRequest(system="S", context="c", instruction="I")
        )
    rec = builder.finalize().call_records[0]
    assert rec.status == CallStatus.TIMEOUT.value


def test_unexpected_error_is_wrapped_as_model_error() -> None:
    backend = FakeBackend(raise_exc=RuntimeError("gpu fell over"))
    builder = _builder()
    client = QwenClient(backend, _params(), builder)
    client.begin_interaction(1, "seq-1")
    with pytest.raises(ModelError):
        client.appraisal_client()(
            AppraisalRequest(system="S", evidence_observation="o", active_hypotheses=(), instruction="I")
        )
    rec = builder.finalize().call_records[0]
    assert rec.status == CallStatus.MODEL_ERROR.value


def test_retries_are_recorded_then_exhausted() -> None:
    backend = FakeBackend(raise_exc=ModelTimeout("slow"))
    builder = _builder()
    client = QwenClient(backend, _params(), builder, retries=2)
    client.begin_interaction(1, "seq-1")
    with pytest.raises(RetryExhaustedError):
        client.extraction_client()(
            ExtractionRequest(system="S", transcript_text="t", instruction="I")
        )
    assert len(backend.calls) == 3  # initial + 2 retries
    rec = builder.finalize().call_records[0]
    assert rec.status == CallStatus.RETRY_EXHAUSTED.value
    assert rec.attempts == 3


def test_runtime_info_is_exposed_for_the_manifest() -> None:
    backend = FakeBackend()
    client = QwenClient(backend, _params(), _builder())
    info = client.runtime_info()
    assert info.backend_id == "fake-offline"
    assert info.model_id == "qwen3-4b"


def test_detect_local_qwen_reports_unavailable_without_config() -> None:
    saved = os.environ.pop("SANUVIA_QWEN_MODEL_PATH", None)
    try:
        avail = detect_local_qwen()
        # This host has no local runtime/artifact configured.
        assert avail.available is False
        assert "no local Qwen runtime" in avail.reason or "no model artifact" in avail.reason
        assert avail.artifact.availability == Availability.NOT_PROVIDED_BY_PROVIDER
    finally:
        if saved is not None:
            os.environ["SANUVIA_QWEN_MODEL_PATH"] = saved


def test_detect_local_qwen_sees_a_configured_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "qwen3-4b.gguf"
    artifact.write_bytes(b"not a real model")
    saved = os.environ.get("SANUVIA_QWEN_MODEL_PATH")
    os.environ["SANUVIA_QWEN_MODEL_PATH"] = str(artifact)
    try:
        avail = detect_local_qwen()
        assert avail.artifact.availability == Availability.AVAILABLE
        assert avail.artifact.value == str(artifact)
        # still not "available" overall unless a runtime is also present
    finally:
        if saved is None:
            os.environ.pop("SANUVIA_QWEN_MODEL_PATH", None)
        else:
            os.environ["SANUVIA_QWEN_MODEL_PATH"] = saved


def test_llama_cpp_version_output_exposes_build_and_commit() -> None:
    assert _normalise_llama_cpp_build("version: 10721 (8e53fcefd)\n") == (
        "build 10721 (commit 8e53fcefd)"
    )
