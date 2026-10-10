"""End-to-end (offline) wiring of the Qwen client to all four boundaries, proving
every real call is captured in the manifest and the three information conditions
stay separated (stateless isolation vs transcript accumulation; no Sanuvia state
leaks to the baselines)."""

from __future__ import annotations

import json

from fixtures.longitudinal.case_001_transcript import CASE_001_TRANSCRIPT

from sanuvia_phase1 import pipeline
from sanuvia_phase1.failures import CallStatus, Maybe
from sanuvia_phase1.manifest import RunManifestBuilder
from sanuvia_phase1.qwen import (
    GenerationParams,
    QwenClient,
    QwenRuntimeInfo,
    qwen_real_run_config,
)


class DispatchingBackend:
    """One offline backend that answers each boundary with valid JSON, chosen from
    the prompt's SYSTEM marker. Records every prompt it is shown."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def describe(self) -> QwenRuntimeInfo:
        return QwenRuntimeInfo(
            "fake-offline", "qwen3-4b", Maybe.available("fake-1"),
            Maybe.available("/models/fake.gguf"), 8192,
        )

    def generate(self, prompt: str, params: GenerationParams) -> str:
        self.prompts.append(prompt)
        if "extract EVIDENCE" in prompt:
            return json.dumps(
                {"evidence": [{"observation": "obs", "evidence_class": "reflective",
                               "reliability": 0.7, "classification_confidence": 0.8,
                               "provenance_confidence": 0.8, "text_span": None}]}
            )
        if "APPRAISE" in prompt:
            return "{}"  # valid empty appraisal (no proposals)
        return json.dumps(
            {"best_explanations": ["e"], "competing_hypotheses_held": [],
             "question_asked": None, "continuity_claims": []}
        )


def _run() -> tuple[RunManifestBuilder, DispatchingBackend]:
    backend = DispatchingBackend()
    builder = RunManifestBuilder(
        run_id="qwen-e2e", created_at="2026-01-01T00:00:00Z", git_commit_sha="sha",
        phase1_version="0.1.0", mode="real", transcript=CASE_001_TRANSCRIPT,
        model_specs=qwen_real_run_config().specs(),
    )
    client = QwenClient(
        backend,
        GenerationParams(temperature=0.0, max_output_tokens=128, context_tokens=4096, seed=0),
        builder,
    )
    pipeline.run_transcript_demonstration(
        CASE_001_TRANSCRIPT,
        client.as_extractor(),
        {},
        {},
        client.as_stateless_model(),
        client.as_transcript_model(),
        case_id="qwen-e2e",
        mode=pipeline.REAL,
        appraiser=client.as_appraiser(),
        config=qwen_real_run_config(),
        on_interaction_start=client.begin_interaction,
    )
    return builder, backend


def test_all_four_boundaries_are_captured_in_the_manifest() -> None:
    builder, _ = _run()
    manifest = builder.finalize()
    boundaries = {r.boundary for r in manifest.call_records}
    assert boundaries == {
        "evidence_extraction", "evidence_appraisal",
        "stateless_baseline", "transcript_baseline",
    }
    # every recorded call succeeded and captured its raw response
    for rec in manifest.call_records:
        assert rec.status == CallStatus.SUCCESS.value
        assert rec.raw_response is not None
        assert rec.seq_label in {i.seq_label for i in CASE_001_TRANSCRIPT.interactions}


def test_per_interaction_status_all_success_including_hold() -> None:
    builder, _ = _run()
    manifest = builder.finalize()
    statuses = dict(manifest.per_interaction_status)
    for interaction in CASE_001_TRANSCRIPT.interactions:
        assert statuses[interaction.seq_label] == CallStatus.SUCCESS.value


def test_expected_call_counts_per_boundary() -> None:
    builder, _ = _run()
    manifest = builder.finalize()
    counts: dict[str, int] = {}
    for rec in manifest.call_records:
        counts[rec.boundary] = counts.get(rec.boundary, 0) + 1
    non_hold = sum(1 for i in CASE_001_TRANSCRIPT.interactions if i.text.strip())
    n = len(CASE_001_TRANSCRIPT.interactions)
    assert counts["evidence_extraction"] == non_hold   # holds consult no model
    assert counts["stateless_baseline"] == n
    assert counts["transcript_baseline"] == n
    assert counts["evidence_appraisal"] >= 1


def test_baselines_receive_no_sanuvia_structured_state() -> None:
    _, backend = _run()
    baseline_prompts = [p for p in backend.prompts if "reasoning baseline condition" in p]
    for prompt in baseline_prompts:
        # no engine evidence ids, no hypothesis/support structure, no dependency graph
        assert "evidence-" not in prompt
        assert "supporting_evidence" not in prompt
        assert "hypothesis_id" not in prompt
        assert "model_version" not in prompt


def test_stateless_isolation_vs_transcript_accumulation() -> None:
    _, backend = _run()
    baseline_prompts = [p for p in backend.prompts if "reasoning baseline condition" in p]
    t1 = CASE_001_TRANSCRIPT.interactions[0].text
    t2 = CASE_001_TRANSCRIPT.interactions[1].text
    assert t1 and t2
    # transcript-context: some baseline prompt carries BOTH turn-1 and turn-2 text
    assert any((t1 in p and t2 in p) for p in baseline_prompts)
    # stateless: some baseline prompt carries turn-2 but NOT turn-1 (fresh context)
    assert any((t2 in p and t1 not in p) for p in baseline_prompts)
