"""Documentation-consistency checks: the Phase 1 experiment manifest must stay in
sync with the implemented prompt/schema registry (ids + hashes) and must state the
key protocol invariants. Guards against the approval doc drifting from the code."""

from __future__ import annotations

from pathlib import Path

from sanuvia_phase1 import prompts

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
    # case, freeze rule, no-invented-threshold posture, local-only, diagnostic-only
    assert "Case 001" in text
    assert "PENDING GOVERNANCE" in text
    assert "local_qwen" in text
    assert "DIAGNOSTIC ONLY" in text
    assert "not been executed" in text or "not been run" in text


def test_protocol_marks_scale_as_proposed_not_authoritative() -> None:
    text = _PROTOCOL.read_text(encoding="utf-8")
    # a numeric scale must be labelled proposed, never authoritative
    assert "PROPOSED — REQUIRES APPROVAL" in text
    for dimension in (
        "Hypothesis continuity", "Hypothesis revision", "Evidence grounding",
        "Uncertainty handling", "Inquiry quality",
    ):
        assert dimension in text
