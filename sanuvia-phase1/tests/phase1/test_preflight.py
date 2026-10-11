"""REAL-evaluation preflight — PASS/BLOCKED gating with clear reasons, no run."""

from __future__ import annotations

import dataclasses

from sanuvia_phase1 import preflight
from sanuvia_phase1.failures import Maybe
from sanuvia_phase1.preflight import BLOCKED, PASS, run_real_preflight
from sanuvia_phase1.qwen import QwenAvailability, qwen_real_run_config
from sanuvia_phase1.runconfig import RealRunConfig

_FROZEN_ARTIFACT_SHA256 = (
    "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
)
_FROZEN_LLAMA_CPP_BUILD = "build 10721 (commit 8e53fcefd)"


#: The authorized participant roster. REAL refuses an empty one, so every
#: preflight that expects the config checks to PASS must state it.
_PARTICIPANTS = ("pA", "pB")


def _configured() -> RealRunConfig:
    return qwen_real_run_config(participants=_PARTICIPANTS)


def _check(result: preflight.PreflightResult, name: str) -> preflight.Check:
    return next(c for c in result.checks if c.name == name)


def _unavailable() -> QwenAvailability:
    return QwenAvailability(
        available=False, reason="no runtime/artifact", model_id="qwen3-4b",
        artifact=Maybe.not_provided_by_provider(),
    )


def _available() -> QwenAvailability:
    # A fully-ready environment whose local artifact/runtime identities match the
    # frozen governance record.
    return QwenAvailability(
        available=True, reason="llama.cpp present and artifact configured",
        model_id="qwen3-4b", artifact=Maybe.available("/models/qwen3-4b.gguf"),
        runtimes_present=("llama_cpp",),
        artifact_sha256=Maybe.available(_FROZEN_ARTIFACT_SHA256),
        llama_cpp_build=Maybe.available(_FROZEN_LLAMA_CPP_BUILD),
    )


def test_blocked_without_a_local_model() -> None:
    result = run_real_preflight(_configured(), availability=_unavailable())
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
        participants=_PARTICIPANTS,
    )
    result = run_real_preflight(config, availability=_available())
    assert _check(result, "model_installed_available").status == PASS
    assert _check(result, "model_version_identifiable").status == PASS
    # governance is frozen and the environment is ready -> nothing is blocked.
    blocked = {c.name for c in result.checks if c.status == BLOCKED}
    assert blocked == set()
    assert result.overall == PASS


def test_incomplete_config_blocks() -> None:
    cfg = _configured()
    holey = dataclasses.replace(
        cfg, extraction=dataclasses.replace(cfg.extraction, provider="")
    )
    result = run_real_preflight(holey, availability=_available())
    assert _check(result, "real_run_config_complete").status == BLOCKED
    assert result.overall == BLOCKED


def test_wrong_artifact_sha_blocks() -> None:
    availability = dataclasses.replace(
        _available(), artifact_sha256=Maybe.available("a" * 64)
    )
    result = run_real_preflight(_configured(), availability=availability)
    check = _check(result, "artifact_sha256_recorded")
    assert check.status == BLOCKED
    assert "mismatch" in check.detail
    assert result.overall == BLOCKED


def test_wrong_llama_cpp_build_blocks() -> None:
    availability = dataclasses.replace(
        _available(),
        llama_cpp_build=Maybe.available("build 10720 (commit deadbeef)"),
    )
    result = run_real_preflight(_configured(), availability=availability)
    check = _check(result, "llama_cpp_build_matches_frozen")
    assert check.status == BLOCKED
    assert "mismatch" in check.detail
    assert result.overall == BLOCKED


def test_render_explains_what_is_missing() -> None:
    text = run_real_preflight(_configured(), availability=_unavailable()).render()
    assert "OVERALL: BLOCKED" in text
    assert "model_installed_available" in text
    assert "Nothing was downloaded or executed" in text


def test_import_isolation_is_checked() -> None:
    result = run_real_preflight(_configured(), availability=_available())
    assert _check(result, "phase0_import_frozen").status == PASS


def test_preflight_blocks_when_the_participant_roster_is_unconfigured() -> None:
    """The REAL-mode prerequisite, stated by the preflight rather than
    discovered mid-run.

    ``qwen_real_run_config()`` deliberately defaults to an empty roster: who is
    authorized is a property of the case, not of the model configuration, so
    the config will not invent one. The preflight's job is to say so plainly.
    """
    result = run_real_preflight(qwen_real_run_config(), availability=_available())

    check = _check(result, "no_scripted_doubles_in_real")
    assert check.status == BLOCKED
    assert "participants" in check.detail
    assert result.overall == BLOCKED


def test_preflight_passes_the_same_config_once_the_roster_is_stated() -> None:
    """The converse, so the check above is attributable to the roster alone."""
    result = run_real_preflight(_configured(), availability=_available())

    assert _check(result, "no_scripted_doubles_in_real").status == PASS
