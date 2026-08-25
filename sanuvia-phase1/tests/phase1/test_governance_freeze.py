"""Governance / freeze record: structure, blocking logic, immutability hash,
name-free wording, and integration with preflight, manifest, and the CLI."""

from __future__ import annotations

from pathlib import Path

from sanuvia_phase1 import governance, prompts
from sanuvia_phase1.__main__ import main
from sanuvia_phase1.governance import GovernanceStatus
from sanuvia_phase1.manifest import RunManifestBuilder
from sanuvia_phase1.preflight import BLOCKED, run_real_preflight
from sanuvia_phase1.qwen import qwen_real_run_config
from sanuvia_phase1.transcript import Transcript, TranscriptInteraction

# Immutability anchor — changing any FROZEN key/value/blocking flag changes this.
_EXPECTED_FREEZE_HASH = "8a8841ba3003bbab0aadff8fa0f3ccceab6ec965cf209d5cc2f77ae30a91a44f"

_BLOCKING_KEYS = {
    "model_artifact_version", "serving_runtime_backend", "quantization",
    "temperature", "seed", "retry_policy", "c4_c5_interpretation",
    "negative_result_disposition",
}


def test_no_pending_value_is_invented() -> None:
    # every pending item has value None (nothing silently chosen)
    for item in governance.pending_items():
        assert item.status is GovernanceStatus.PENDING_GOVERNANCE_APPROVAL
        assert item.value is None
    # every frozen item carries a concrete value and a source citation
    for item in governance.frozen_items():
        assert item.value
        assert item.source


def test_blocking_items_and_run_not_permitted() -> None:
    assert {i.key for i in governance.blocking_items()} == _BLOCKING_KEYS
    assert governance.is_real_run_permitted() is False
    # eval_hardware is pending but explicitly non-blocking
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


def test_c4_c5_and_negative_result_remain_pending() -> None:
    pending_keys = {i.key for i in governance.pending_items()}
    assert "c4_c5_interpretation" in pending_keys
    assert "negative_result_disposition" in pending_keys


def test_render_is_name_free() -> None:
    text = governance.render_checklist()
    for name in ("Lillian", "Felix", "Claude", "Codex", "ChatGPT"):
        assert name not in text
    assert "FROZEN / APPROVED" in text
    assert "PENDING GOVERNANCE APPROVAL" in text
    assert "BLOCKING THE REAL RUN" in text


def test_preflight_includes_governance_gate() -> None:
    result = run_real_preflight(qwen_real_run_config())
    gate = next(c for c in result.checks if c.name == "governance_freeze_complete")
    assert gate.status == BLOCKED
    for key in _BLOCKING_KEYS:
        assert key in gate.detail


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


def test_cli_governance_reports_blocked() -> None:
    assert main(["governance"]) == 2       # blocked (pending items)
    assert main(["preflight-real"]) == 2   # blocked (governance + model)


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
