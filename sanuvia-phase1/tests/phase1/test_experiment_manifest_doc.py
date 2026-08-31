"""Documentation-consistency checks: the Phase 1 experiment manifest must stay in
sync with the implemented prompt/schema registry (ids + hashes) and must state the
key protocol invariants. Guards against the approval doc drifting from the code."""

from __future__ import annotations

from pathlib import Path

from sanuvia_phase1 import governance, prompts

_DOCS = Path(__file__).resolve().parents[2] / "docs"
_MANIFEST = _DOCS / "phase1-experiment-manifest.md"
_PROTOCOL = _DOCS / "phase1-semantic-evaluation-protocol.md"


def _manifest_text() -> str:
    return _MANIFEST.read_text(encoding="utf-8")


def test_docs_exist() -> None:
    assert _MANIFEST.is_file()
    assert _PROTOCOL.is_file()


def test_manifest_lists_every_prompt_id_and_hash() -> None:
    text = _manifest_text()
    for pid, spec in prompts.PROMPTS.items():
        assert pid in text, f"manifest missing prompt id {pid}"
        assert spec.content_sha256 in text, f"manifest missing hash for {pid}"


def test_manifest_lists_every_schema_id_and_hash() -> None:
    text = _manifest_text()
    for sid, spec in prompts.SCHEMAS.items():
        assert sid in text, f"manifest missing schema id {sid}"
        assert spec.content_sha256 in text, f"manifest missing hash for {sid}"


def test_manifest_states_core_invariants() -> None:
    text = _manifest_text()
    # three conditions
    for name in ("sanuvia_persistent", "fm_stateless", "fm_transcript"):
        assert name in text
    # case, freeze rule, local-only, diagnostic-only, and no inference yet
    assert "Case 001" in text
    assert "local_qwen" in text
    assert "DIAGNOSTIC ONLY" in text
    assert "not been executed" in text or "not been run" in text


def test_manifest_matches_verified_run001_governance() -> None:
    text = _manifest_text()
    frozen = {item.key: item.value for item in governance.frozen_items()}
    assert governance.FREEZE_RECORD_VERSION in text
    artifact_sha256 = frozen["artifact_sha256"]
    assert artifact_sha256 is not None and artifact_sha256 in text
    build = frozen["llama_cpp_build"]
    assert build is not None and build in text
    assert "artifact identification pending" not in text.casefold()
    assert "No model has been downloaded" not in text
    assert "exact version" in text and "**PENDING** (blocking)" not in text


def test_protocol_lists_dimensions_and_approved_scale() -> None:
    text = _PROTOCOL.read_text(encoding="utf-8")
    # the 0–2 scale is now a governance decision approved for Run 001
    assert "APPROVED (Run 001)" in text
    assert "0–2 ordinal" in text
    for dimension in (
        "Hypothesis continuity", "Hypothesis revision", "Evidence grounding",
        "Uncertainty handling", "Inquiry quality",
    ):
        assert dimension in text
