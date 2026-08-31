"""Governance / freeze record: structure, blocking logic, immutability hash,
name-free wording, and integration with preflight, manifest, and the CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from sanuvia_phase1 import governance, prompts
from sanuvia_phase1.__main__ import main
from sanuvia_phase1.governance import GovernanceStatus
from sanuvia_phase1.manifest import RunManifestBuilder
from sanuvia_phase1.preflight import PASS, run_real_preflight
from sanuvia_phase1.qwen import qwen_real_run_config
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction

# Immutability anchor — changing the version or any FROZEN key/value/blocking flag
# changes this. Updated for freeze record v3.0-run001-verified (artifact verified).
_EXPECTED_FREEZE_HASH = "3f46ef56e12c776251a223180cfbf842f228fbbcb743ff5c466f7acf45c0a2dd"

# The verified artifact/digest are now frozen; no blocking items remain.
_BLOCKING_KEYS: set[str] = set()


def test_no_pending_value_is_invented() -> None:
    # every pending item has value None (nothing silently chosen)
    for item in governance.pending_items():
        assert item.status is GovernanceStatus.PENDING_GOVERNANCE_APPROVAL
        assert item.value is None
    # every frozen item carries a concrete value and a source citation
    for item in governance.frozen_items():
        assert item.value
        assert item.source


def test_no_blocking_items_and_run_permitted() -> None:
    assert {i.key for i in governance.blocking_items()} == _BLOCKING_KEYS  # empty
    assert governance.is_real_run_permitted() is True
    # only eval_hardware remains pending, and it is explicitly non-blocking
    assert {i.key for i in governance.pending_items()} == {"eval_hardware"}
    hardware = next(i for i in governance.pending_items() if i.key == "eval_hardware")
    assert hardware.blocking is False


def test_freeze_hash_is_stable() -> None:
    assert governance.freeze_record_sha256() == _EXPECTED_FREEZE_HASH


def test_prompt_schema_versions_are_pinned_to_registry() -> None:
    frozen = {i.key: i.value for i in governance.frozen_items()}
    extractor = frozen["extractor_prompt_version"]
    assert extractor is not None
    assert prompts.EXTRACTION_PROMPT_ID in extractor
    assert prompts.prompt(prompts.EXTRACTION_PROMPT_ID).content_sha256 in extractor
    # both baselines pin the SAME shared baseline prompt
    assert frozen["stateless_prompt_version"] == frozen["transcript_prompt_version"]


def test_semantic_constraints_are_frozen() -> None:
    frozen_keys = {i.key for i in governance.frozen_items()}
    for key in (
        "observation_vs_interpretation", "resonance_not_accuracy", "provenance_limits",
        "retain_competing_hypotheses", "empty_hold_preserved", "do_not_engineer_h1_h4",
        "retain_observed_h1_h2", "golden_is_structural_control",
    ):
        assert key in frozen_keys


def test_run001_governance_decisions_are_frozen() -> None:
    frozen = {i.key: i.value for i in governance.frozen_items()}
    # C.4/C.5 and negative-result disposition are now approved (frozen), not pending.
    assert "c4_c5_interpretation" in frozen
    assert "negative_result_disposition" in frozen
    assert frozen["temperature"] == "0.0"
    assert frozen["seed"] == "0 (fixed)"
    assert frozen["retry_policy"] == "0 (Run 001)"
    assert frozen["quantization"] == "Q4_K_M"
    assert frozen["serving_runtime_backend"] == "llama.cpp (GGUF)"
    assert frozen["model_family"] == "Qwen3-4B"
    assert frozen["context_window"] == "8192"
    assert frozen["max_output_tokens"] == "512"
    assert frozen["stop_sequences"] == "none"
    # approved semantic protocol pinned
    for key in ("semantic_dimensions", "semantic_scale", "semantic_evaluators", "semantic_blinding"):
        assert key in frozen
    # C.4/C.5 explicitly records raw-observables-only, no aggregate/threshold/pass-fail
    c45 = frozen["c4_c5_interpretation"]
    assert c45 is not None and "raw longitudinal observables only" in c45


def test_verified_artifact_and_runtime_are_frozen() -> None:
    frozen = {i.key: i.value for i in governance.frozen_items()}
    mav = frozen["model_artifact_version"]
    assert mav is not None
    assert "Qwen/Qwen3-4B-GGUF@bc640142c66e1fdd12af0bd68f40445458f3869b" in mav
    assert "Qwen3-4B-Q4_K_M.gguf" in mav and "2497280256" in mav
    assert frozen["artifact_sha256"] == (
        "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
    )
    build = frozen["llama_cpp_build"]
    assert build is not None and "10721" in build and "8e53fcefd" in build


def test_render_is_name_free() -> None:
    text = governance.render_checklist()
    for name in ("Lillian", "Felix", "Claude", "Codex", "ChatGPT"):
        assert name not in text
    assert "FROZEN / APPROVED" in text
    assert "PENDING GOVERNANCE APPROVAL" in text
    assert "BLOCKING THE REAL RUN" in text


def test_preflight_governance_gate_passes_when_frozen() -> None:
    result = run_real_preflight(qwen_real_run_config())
    gate = next(c for c in result.checks if c.name == "governance_freeze_complete")
    # all blocking governance items are now frozen/approved
    assert gate.status == PASS


def test_manifest_can_pin_the_freeze_hash() -> None:
    from sanuvia.domain import SubjectId, shared_space_id

    transcript = Transcript(
        "t", SubjectId("s"), shared_space_id("x"),
        (TranscriptInteraction(1, "seq-1", "hi"),),
    )
    builder = RunManifestBuilder(
        run_id="r", created_at="2026-01-01T00:00:00Z", git_commit_sha="sha",
        phase1_version="0.1.0", mode="real", transcript=transcript,
        governance_freeze_hash=governance.freeze_record_sha256(),
    )
    manifest = builder.finalize()
    assert manifest.governance_freeze_hash == _EXPECTED_FREEZE_HASH
    assert _EXPECTED_FREEZE_HASH in manifest.to_json()


def test_cli_governance_permitted(monkeypatch: pytest.MonkeyPatch) -> None:
    # governance freeze is complete -> the governance checklist exits 0 (permitted)
    assert main(["governance"]) == 0
    # preflight-real still depends on the runtime env; without the model path set it
    # remains blocked on model availability (exit 2), independent of governance.
    monkeypatch.delenv("SANUVIA_QWEN_MODEL_PATH", raising=False)
    assert main(["preflight-real"]) == 2


# --- documentation consistency -------------------------------------------------

_DOC = Path(__file__).resolve().parents[2] / "docs" / "phase1-governance-freeze-record.md"


def test_doc_lists_every_key_and_the_freeze_hash() -> None:
    text = _DOC.read_text(encoding="utf-8")
    assert governance.freeze_record_sha256() in text
    for item in governance.FREEZE_RECORD:
        assert item.key in text, f"governance doc missing key {item.key}"
    for section in ("Frozen / approved", "Pending governance approval", "Blocking the real run"):
        assert section in text
    assert "No real Qwen run has occurred" in text
