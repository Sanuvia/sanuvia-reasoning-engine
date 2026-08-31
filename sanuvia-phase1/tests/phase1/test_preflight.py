"""REAL-evaluation preflight — PASS/BLOCKED gating with clear reasons, no run."""

from __future__ import annotations

import dataclasses

from sanuvia_phase1 import preflight
from sanuvia_phase1.failures import Maybe
from sanuvia_phase1.preflight import BLOCKED, PASS, run_real_preflight
from sanuvia_phase1.qwen import QwenAvailability, qwen_real_run_config


def _check(result: preflight.PreflightResult, name: str) -> preflight.Check:
    return next(c for c in result.checks if c.name == name)


def _unavailable() -> QwenAvailability:
    return QwenAvailability(
        available=False, reason="no runtime/artifact", model_id="qwen3-4b",
        artifact=Maybe.not_provided_by_provider(),
    )


def _available() -> QwenAvailability:
    # A fully-ready environment: llama.cpp runtime present, artifact configured and
    # hashed. (Governance still blocks until the exact version/digest are recorded.)
    return QwenAvailability(
        available=True, reason="llama.cpp present and artifact configured",
        model_id="qwen3-4b", artifact=Maybe.available("/models/qwen3-4b.gguf"),
        runtimes_present=("llama_cpp",),
        artifact_sha256=Maybe.available("a" * 64),
    )


def test_blocked_without_a_local_model() -> None:
    result = run_real_preflight(qwen_real_run_config(), availability=_unavailable())
    assert result.overall == BLOCKED
    assert _check(result, "model_installed_available").status == BLOCKED
    assert _check(result, "model_version_identifiable").status == BLOCKED
    # the non-model checks are already satisfied
    assert _check(result, "real_run_config_complete").status == PASS
    assert _check(result, "prompts_present").status == PASS
    assert _check(result, "prompt_integrity_no_drift").status == PASS
    assert _check(result, "schemas_present").status == PASS
    assert _check(result, "no_scripted_doubles_in_real").status == PASS
    assert _check(result, "no_network_dependency").status == PASS
    assert _check(result, "phase0_import_frozen").status == PASS


def test_model_checks_flip_when_available_and_versioned() -> None:
    config = qwen_real_run_config(
        model_version=Maybe.available("qwen3-4b-q4_k_m@abc123"),
        artifact_id=Maybe.available("/models/qwen3-4b.gguf"),
        backend_id="llama_cpp",
    )
    result = run_real_preflight(config, availability=_available())
    assert _check(result, "model_installed_available").status == PASS
    assert _check(result, "model_version_identifiable").status == PASS
    # governance is frozen and the environment is ready -> nothing is blocked.
    blocked = {c.name for c in result.checks if c.status == BLOCKED}
    assert blocked == set()
    assert result.overall == PASS


def test_incomplete_config_blocks() -> None:
    cfg = qwen_real_run_config()
    holey = dataclasses.replace(
        cfg, extraction=dataclasses.replace(cfg.extraction, provider="")
    )
    result = run_real_preflight(holey, availability=_available())
    assert _check(result, "real_run_config_complete").status == BLOCKED
    assert result.overall == BLOCKED


def test_render_explains_what_is_missing() -> None:
    text = run_real_preflight(qwen_real_run_config(), availability=_unavailable()).render()
    assert "OVERALL: BLOCKED" in text
    assert "model_installed_available" in text
    assert "Nothing was downloaded or executed" in text


def test_import_isolation_is_checked() -> None:
    result = run_real_preflight(qwen_real_run_config(), availability=_available())
    assert _check(result, "phase0_import_frozen").status == PASS
